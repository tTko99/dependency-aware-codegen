from __future__ import annotations

import json
import time
from dataclasses import replace

from depguard.agent.contracts import AgentState, ToolCall, ToolResult, ToolSpec, code_hash
from depguard.agent.patching import apply_patch, rollback
from depguard.agent.safety import guard_tool
from depguard.analysis import DependencyAnalyzer
from depguard.execution import SandboxedExecutor
from depguard.schemas import to_jsonable
from depguard.verification import APIVerifier, PackageVerifier


class ProtocolError(ValueError):
    pass


def action_fingerprint(state, call):
    return code_hash(json.dumps([call.name, call.arguments, state.version, state.context_version],
                                sort_keys=True, separators=(",", ":"), allow_nan=False))


def execution_fingerprint(state, name):
    # A changed rerun_reason alone must never bypass execution idempotency.
    return f"execution:{name}:{state.version}:{state.context_version}"


class ToolRegistry:
    def __init__(self):
        self.entries = {}

    def register(self, spec, handler):
        if spec.name in self.entries:
            raise ValueError(f"duplicate tool: {spec.name}")
        self.entries[spec.name] = (spec, handler)

    @property
    def specs(self):
        return [entry[0] for entry in self.entries.values()]

    def validate(self, call):
        if (not isinstance(call, ToolCall) or not isinstance(call.name, str)
                or call.name not in self.entries):
            raise ProtocolError("Choose exactly one registered tool")
        spec, _ = self.entries[call.name]
        args = call.arguments
        schema = spec.parameters
        if not isinstance(args, dict) or set(args) - set(schema["properties"]):
            raise ProtocolError("Unknown arguments or non-object arguments")
        try:
            json.dumps(args, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ProtocolError("Arguments must contain only legal JSON values") from exc
        if set(schema.get("required", [])) - set(args):
            raise ProtocolError("Missing required arguments")
        for key, value in args.items():
            expected = schema["properties"][key]["type"]
            types = {"string": str, "boolean": bool, "integer": int,
                     "number": (int, float), "object": dict, "array": list}
            if (expected not in types or not isinstance(value, types[expected])
                    or expected in {"integer", "number"} and isinstance(value, bool)):
                raise ProtocolError(f"{key} must be a {expected}")
            if "enum" in schema["properties"][key] and value not in schema["properties"][key]["enum"]:
                raise ProtocolError(f"{key} must be an allowed outcome")
        return spec

    def dispatch(self, state, call, *, deadline):
        spec = self.validate(call)
        refusal = guard_tool(state, spec)
        if refusal:
            result = replace(refusal, candidate_version=state.version)
            self._record_check(state, call.name, result)
            return self._with_summary(state, result)
        key = action_fingerprint(state, call)
        count = state.call_counts.get(key, 0)
        state.call_counts[key] = count + 1
        execution_key = execution_fingerprint(state, call.name)
        execution_count = state.call_counts.get(execution_key, 0)
        previous = state.last_execution_results.get(execution_key)
        retry_error = previous is not None and previous.status == "error"
        if (execution_count and call.name in {"execute", "run_pytest"}
                and not retry_error and not state.allow_test_rerun):
            return self._with_summary(state, ToolResult("denied",
                "Unchanged test run: change candidate/config or enable rerun", candidate_version=state.version))
        if call.name in {"execute", "run_pytest"}:
            state.call_counts[execution_key] = execution_count + 1
        if spec.cacheable and key in state.cache:
            result = replace(state.cache[key], cached=True)
            self._record_check(state, call.name, result)
            return self._with_summary(state, result)
        try:
            result = self.entries[call.name][1](state, call.arguments, deadline)
        except Exception as exc:  # noqa: BLE001 - convert boundary failures to observations
            result = ToolResult("error", f"{type(exc).__name__}: {exc}",
                                {"kind": "tool_error", "retry_allowed": True})
        result = replace(result, candidate_version=state.version)
        if call.name in {"execute", "run_pytest"}:
            state.last_execution_results[execution_key] = result
        self._record_check(state, call.name, result)
        if spec.cacheable and result.status == "success":
            state.cache[key] = result
        return self._with_summary(state, result)

    @staticmethod
    def _with_summary(state, result):
        from depguard.agent.validation_state import validation_summary
        return replace(result, evidence={**result.evidence, "validation_state": validation_summary(state)})

    @staticmethod
    def _record_check(state, name, result):
        if name in state.required_checks:
            state.check_results[name] = result
            state.check_result_contexts[name] = state.context_version
        if result.status == "success" and result.evidence.get("passed") is True:
            state.passed_checks[name] = state.version
            state.check_state_versions[name] = state.context_version
        else:
            state.passed_checks.pop(name, None)
            state.check_state_versions.pop(name, None)


def validate_packages(state, args, deadline):
    refusal = guard_tool(state, ToolSpec("validate_packages", "", {}, ("read_source",)))
    if refusal:
        return refusal
    analysis = DependencyAnalyzer().analyze(state.candidate_code)
    rows = PackageVerifier().verify_imports(analysis.imports)
    return ToolResult("success", "Package validation", {
        "passed": not analysis.syntax_error and all(row.exists for row in rows),
        "syntax_error": analysis.syntax_error, "results": to_jsonable(rows),
    })


def validate_apis(state, args, deadline):
    refusal = guard_tool(state, ToolSpec("validate_apis", "", {}, ("read_source", "execute")))
    if refusal:
        return refusal
    analysis = DependencyAnalyzer().analyze(state.candidate_code)
    rows = APIVerifier().verify_many(analysis.api_references) if not analysis.syntax_error else []
    return ToolResult("success", "API validation", {
        "passed": not analysis.syntax_error and all(row.api_valid for row in rows),
        "syntax_error": analysis.syntax_error, "results": to_jsonable(rows),
    })


def execute(state, args, deadline):
    return _execute(state, None, deadline)


def run_pytest(state, args, deadline):
    if not state.test_code:
        return ToolResult("denied", "No tests supplied")
    return _execute(state, state.test_code, deadline)


def _execute(state, tests, deadline):
    name = "run_pytest" if tests is not None else "execute"
    permissions = ("read_source", "execute", "write_temp")
    if tests is not None:
        permissions += ("read_tests",)
    refusal = guard_tool(state, ToolSpec(name, "", {}, permissions))
    if refusal:
        return refusal
    timeout = min(state.execution_timeout_seconds, max(.001, deadline - time.monotonic()))
    result = SandboxedExecutor(timeout_seconds=timeout).execute(
        state.candidate_code, test_code=tests,
    )
    return ToolResult("success", "Execution completed", {
        "passed": result.status == "passed", "execution": to_jsonable(result),
    })


def finish(state, args, deadline):
    from depguard.agent.regression import verification
    from depguard.agent.validation_state import finish_outcome, validation_summary

    report = verification(state)
    summary = validation_summary(state)
    outcome = finish_outcome(args)
    evidence = {**report, "conclusion": args.get("conclusion", ""),
                "claimed_success": outcome == "success", "outcome": outcome,
                "validation_state": summary}
    if outcome == "success" and not summary["ready_to_finish_successfully"]:
        states = summary["required_checks"]
        evidence.update(error_code="FINISH_PRECONDITION_FAILED",
            missing_checks=[n for n, value in states.items() if value == "missing"],
            failed_checks=[n for n, value in states.items() if value == "failed"],
            stale_checks=[n for n, value in states.items() if value == "stale"],
            allowed_next_tools=sorted({n for n, value in states.items() if value != "passed"}
                | {"apply_patch", "rollback", "finish"}))
        return ToolResult("error", "Success finish rejected; choose validation or repair from the observation. "
                          "Use finish(success=false) to abandon.", evidence)
    return ToolResult("success", "Model submitted conclusion", evidence)


def default_registry():
    registry = ToolRegistry()
    for name, handler, permissions, cacheable, properties, required in [
        ("validate_packages", validate_packages, ("read_source",), True, {}, []),
        ("validate_apis", validate_apis, ("read_source", "execute"), True, {}, []),
        ("execute", execute, ("read_source", "execute", "write_temp"), False,
         {"rerun_reason": {"type": "string"}}, []),
        ("run_pytest", run_pytest, ("read_source", "read_tests", "execute", "write_temp"), False,
         {"rerun_reason": {"type": "string"}}, []),
        ("apply_patch", apply_patch, ("read_source",), False,
         {"patch": {"type": "string"}, "path": {"type": "string"}}, ["patch"]),
        ("rollback", rollback, ("read_source",), False, {}, []),
        ("finish", finish, (), False, {"conclusion": {"type": "string"},
                                      "success": {"type": "boolean"},
                                      "outcome": {"type": "string", "enum": ["success", "failure", "abandoned"]}}, []),
    ]:
        description = ("Finish successfully only when every current-version required check passes and "
            "regression is unblocked. Missing, failed or stale evidence returns an observation; "
            "choose your next tool. To stop unsuccessfully use success=false or outcome=failure."
            if name == "finish" else handler.__name__)
        registry.register(ToolSpec(name, description, {
            "type": "object", "properties": properties, "required": required,
            "additionalProperties": False,
        }, permissions, cacheable), handler)
    return registry


def dispatch_worker(registry: ToolRegistry, state: AgentState, call: ToolCall, deadline: float):
    return registry.dispatch(state, call, deadline=deadline), state
