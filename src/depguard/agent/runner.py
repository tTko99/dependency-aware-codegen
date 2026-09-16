"""Public repair entry: deterministic initial gate, then model-directed repair loop."""
import copy
import time
from dataclasses import replace

from depguard.agent.context import compact_observation
from depguard.agent.contracts import AgentRunResult, ToolCall, code_hash
from depguard.agent.deadline import bounded
from depguard.agent.regression import verification
from depguard.agent.tools import default_registry, dispatch_worker
from depguard.schemas import to_jsonable


def validate_candidate(state, deadline):
    """Independent real validation; no model cache, no changes to candidate or inputs."""
    checked = copy.deepcopy(state)
    checked.call_counts.clear()
    checked.cache.clear()
    checked.passed_checks.clear()
    checked.check_state_versions.clear()
    checked.check_results.clear()
    checked.check_result_contexts.clear()
    checked.allow_test_rerun = True
    evidence = {}
    registry = default_registry()
    for name in sorted(state.required_checks):
        result, checked = bounded(dispatch_worker, (registry, checked, ToolCall(name), deadline), deadline)
        evidence[name] = to_jsonable(result)
    for name in ("passed_checks", "check_state_versions", "check_results", "check_result_contexts"):
        setattr(state, name, getattr(checked, name))
    return {**verification(checked), "checks": evidence}


def run_agent(loop, state, requirement):
    """Never invoke the repair model for a verified original candidate.

    AgentLoop.run remains the low-level continuation API for isolated state-machine
    tests. CLI and live M7.2 evaluation use this gated entry.
    """
    started = time.monotonic()
    if not state.required_checks or not state.required_checks <= {
        "validate_packages", "validate_apis", "execute", "run_pytest"
    }:
        raise ValueError("required_checks must be a nonempty subset of supported validation tools")
    try:
        initial = validate_candidate(state, started + loop.timeout_seconds)
    except TimeoutError:
        return AgentRunResult("INCOMPLETE", "global_timeout", state.candidate_code, state.version,
            [], dict(state.passed_checks), dict(state.input_hashes), time.monotonic()-started,
            loop.model.model_name, agent_invoked=False)
    state.initial_evidence = {**initial, "checks": {name: compact_observation(result, loop.output_limit)
        for name, result in initial["checks"].items()}}
    if (state.candidate_code == state.original_code and not state.applied_patches
            and initial["host_status"] == "PASS"):
        return AgentRunResult("NO_REPAIR_NEEDED", "no_repair_needed", state.candidate_code,
            state.version, [], dict(state.passed_checks), dict(state.input_hashes),
            time.monotonic()-started, loop.model.model_name, agent_invoked=False,
            initial_verification=initial, finish_verification=initial,
            capability_probe={"status": "not_run", "reason": "Initial verification passed; repair not triggered"},
            candidate_revision=state.candidate_revision, candidate_sha256=code_hash(state.candidate_code),
            config_hashes=dict(state.config_hashes), regression_guard=initial["regression_guard"])
    remaining = max(.001, loop.timeout_seconds - (time.monotonic() - started))
    budget = loop.timeout_seconds
    try:
        loop.timeout_seconds = remaining
        result = loop.run(state, requirement)
    finally:
        loop.timeout_seconds = budget
    return replace(result, initial_verification=initial, elapsed_seconds=time.monotonic()-started)
