from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from depguard.analysis import DependencyAnalyzer
from depguard.config import load_config
from depguard.execution import SandboxedExecutor
from depguard.models.hf import HFCausalCodeGenerator, HFCausalRepairModel
from depguard.models.ollama import OllamaRepairModel
from depguard.models.smoke import HeuristicRepairModel, HeuristicSmokeCodeGenerator
from depguard.pipeline import DependencyGuardPipeline
from depguard.schemas import to_jsonable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="depguard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze imports and API references.")
    _add_code_args(analyze_parser)

    run_parser = subparsers.add_parser("run", help="Run generation, validation, execution, and repair.")
    run_parser.add_argument("--requirement", default="", help="Natural-language programming task.")
    run_parser.add_argument("--config", default=None, help="YAML/JSON config path.")
    run_parser.add_argument("--output", default=None, help="Optional JSON output path.")
    run_parser.add_argument("--generator", choices=["hf", "smoke"], default=None)
    run_parser.add_argument(
        "--repair", choices=["none", "hf", "ollama", "heuristic"], default=None
    )
    run_parser.add_argument("--timeout", type=float, default=None)
    run_parser.add_argument(
        "--test-file",
        default=None,
        help="Optional pytest file evaluated against the supplied or generated code.",
    )
    _add_code_args(run_parser)

    agent_parser = subparsers.add_parser("agent", help="Run observation-driven tool repair.")
    agent_parser.add_argument("--code-file", required=True)
    agent_parser.add_argument("--test-file")
    agent_parser.add_argument("--project-root", default=".")
    agent_parser.add_argument("--requirement", default="")
    agent_parser.add_argument("--config", default="configs/engineering_7b_ollama.yaml")
    agent_parser.add_argument("--output")
    agent_parser.add_argument("--max-steps", type=int)
    agent_parser.add_argument("--timeout", type=float)
    agent_parser.add_argument("--recent-steps", type=int)
    agent_parser.add_argument("--agent-provider", choices=["ollama", "cloud", "scripted"])
    agent_parser.add_argument("--agent-model")
    agent_parser.add_argument("--base-url")
    agent_parser.add_argument("--script", help="ScriptedTestModel JSON script (test/demo only).")
    agent_parser.add_argument("--protocol-error-limit", type=int)
    agent_parser.add_argument("--observation-max-length", type=int)
    agent_parser.add_argument("--capability-probe", action=argparse.BooleanOptionalAction, default=None)
    agent_parser.add_argument("--probe-cache", action=argparse.BooleanOptionalAction, default=None)
    agent_parser.add_argument("--trajectory-output", help="Full run artifact including raw results.")
    agent_parser.add_argument("--apply", action="store_true", help="Commit only verified PASS.")
    agent_parser.add_argument("--allow-test-rerun", action="store_true")
    agent_parser.add_argument("--risk-policy", choices=["reject", "mock", "requires_sandbox"],
                              default="reject")
    agent_parser.add_argument("--deny-permission", action="append", default=[], choices=[
        "read_source", "read_tests", "execute", "write_temp", "write_target",
    ])

    args = parser.parse_args(argv)
    if args.command == "agent":
        return _run_agent(args)
    if args.command == "analyze":
        code = _read_code(args)
        result = DependencyAnalyzer().analyze(code)
        print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        _validate_output_path(args)
        config = load_config(args.config)
        code = _read_code(args, required=False)
        test_code = _read_optional_file(args.test_file)
        pipeline = _build_pipeline(config, args)
        result = pipeline.run(requirement=args.requirement, code=code, test_code=test_code)
        payload = to_jsonable(result)
        payload["repair_attempted"] = result.repaired_code is not None
        payload["repair_model_name"] = getattr(pipeline.repair_model, "model_name", None)
        payload["final_status"] = _derive_final_status(result)
        response_metadata = getattr(pipeline.repair_model, "last_response_metadata", None)
        if result.repaired_code is not None and response_metadata:
            payload["repair_backend_metadata"] = dict(response_metadata)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


def _add_code_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--code", help="Python code string.")
    group.add_argument("--code-file", help="Path to Python code file.")


def _read_code(args: argparse.Namespace, *, required: bool = True) -> str | None:
    if getattr(args, "code", None) is not None:
        return args.code
    if getattr(args, "code_file", None):
        return Path(args.code_file).read_text(encoding="utf-8")
    if required:
        raise SystemExit("Provide --code or --code-file.")
    return None


def _read_optional_file(path: str | None) -> str | None:
    return Path(path).read_text(encoding="utf-8") if path else None


def _validate_output_path(args: argparse.Namespace) -> None:
    if not args.output:
        return
    output_path = Path(args.output).resolve()
    protected_paths = [
        Path(path).resolve()
        for path in (getattr(args, "code_file", None), getattr(args, "test_file", None))
        if path
    ]
    if getattr(args, "command", None) == "agent":
        protected_paths += [Path(path).resolve() for path in (
            getattr(args, "config", None), getattr(args, "script", None)) if path]
    if output_path in protected_paths or any(
        output_path.exists() and path.exists() and output_path.samefile(path)
        for path in protected_paths
    ):
        raise SystemExit("--output must not overwrite the source or test input file.")


def _run_agent(args):
    from depguard.agent.loop import AgentLoop
    from depguard.agent.persistence import persist
    from depguard.agent.runner import run_agent
    from depguard.agent.safety import load_state, sha256_file
    from depguard.models.agent import OllamaAgentModel
    from depguard.models.cloud import CloudToolCallingModel
    from depguard.models.scripted import ScriptedTestModel

    _validate_output_path(args)
    if args.trajectory_output:
        trajectory_args = argparse.Namespace(**vars(args))
        trajectory_args.output = args.trajectory_output
        _validate_output_path(trajectory_args)
    permissions = {"read_source", "read_tests", "execute", "write_temp"}
    if args.apply:
        permissions.add("write_target")
    permissions -= set(args.deny_permission)
    config_hash = sha256_file(Path(args.config)) if args.config else None
    config = load_config(args.config)
    agent_config = config.get("agent", {})
    if not config.get("execution", {}).get("enabled", True):
        permissions.discard("execute")
    state = load_state(args.code_file, args.test_file, project_root=args.project_root,
                       permissions=permissions, risk_policy=args.risk_policy,
                       allow_test_rerun=args.allow_test_rerun,
                       execution_timeout_seconds=config.get("execution", {})
                       .get("timeout_seconds", 10),
                       validation_config=agent_config.get("validation", {}),
                       regression_config=agent_config.get("regression_guard", {}),
                       config_paths=[args.config] if args.config else [])
    if args.config and state.config_hashes[str(Path(args.config).resolve())] != config_hash:
        raise SystemExit("CONFIG_INTEGRITY_MISMATCH: configuration changed during startup")
    provider = args.agent_provider or agent_config.get("provider", "ollama")
    if provider == "scripted":
        script = args.script or agent_config.get("script")
        if not script:
            raise SystemExit("Scripted provider requires --script or agent.script")
        model = ScriptedTestModel.from_file(script)
    elif provider in {"cloud", "ollama"}:
        options = dict(agent_config.get(provider, {}) if provider == "cloud" else
                       agent_config.get("ollama", config.get("repair", {}).get("ollama", {})))
        if args.agent_model or agent_config.get("model_name"):
            options["model_name"] = args.agent_model or agent_config["model_name"]
        if args.base_url:
            options["base_url"] = args.base_url
        if provider == "ollama":
            options.setdefault("model_name", "qwen2.5-coder:7b")
            model = OllamaAgentModel(**options)
        else:
            if "model_name" not in options:
                raise SystemExit("Cloud provider requires --agent-model or agent.model_name")
            model = CloudToolCallingModel(**options)
    else:
        raise SystemExit("Unknown agent provider")

    def setting(argument, name, default):
        return argument if argument is not None else agent_config.get(name, default)

    timeout = setting(args.timeout, "timeout_seconds", 180)
    started = time.monotonic()
    loop = AgentLoop(model, max_steps=setting(args.max_steps, "max_steps", 20),
                       timeout_seconds=timeout,
                       recent_steps=setting(args.recent_steps, "recent_steps", 6),
                       protocol_limit=setting(args.protocol_error_limit, "protocol_limit", 3),
                       output_limit=setting(args.observation_max_length, "output_limit", 4000),
                       capability_probe=setting(args.capability_probe, "capability_probe", True),
                       probe_cache=setting(args.probe_cache, "probe_cache", True))
    result = run_agent(loop, state, args.requirement)
    if args.apply and result.final_status != "NO_REPAIR_NEEDED":
        result = persist(state, result, deadline=started + timeout)
    payload = to_jsonable(result)
    for path in {args.output, args.trajectory_output} - {None}:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.final_status in {"PASS", "NO_REPAIR_NEEDED"} else 1


def _derive_final_status(result: Any) -> str:
    repaired = result.repaired_code is not None
    analysis = result.repaired_analysis if repaired else result.analysis
    package_results = result.repaired_package_results if repaired else result.package_results
    api_results = result.repaired_api_results if repaired else result.api_results
    execution_result = (
        result.repaired_execution_result if repaired else result.execution_result
    )
    validation_passed = (
        analysis is not None
        and analysis.syntax_error is None
        and all(package.exists for package in package_results)
        and all(api.api_valid for api in api_results)
    )
    execution_passed = execution_result is None or execution_result.status == "passed"
    if not validation_passed or not execution_passed:
        return "FAIL"
    return "PASS" if repaired else "NO_REPAIR_NEEDED"


def _build_pipeline(config: dict[str, Any], args: argparse.Namespace) -> DependencyGuardPipeline:
    generation_cfg = config.get("generation", {})
    repair_cfg = config.get("repair", {})
    execution_cfg = config.get("execution", {})

    code_provided = bool(getattr(args, "code", None) or getattr(args, "code_file", None))
    generator_kind = None if code_provided else args.generator or generation_cfg.get("kind")
    repair_kind = args.repair or repair_cfg.get("kind", "none")
    generator = None
    if generator_kind is None and not code_provided:
        generator_kind = "hf"
    if generator_kind == "smoke":
        generator = HeuristicSmokeCodeGenerator()
    elif generator_kind == "hf":
        generator = HFCausalCodeGenerator(**generation_cfg.get("hf", {}))

    repair_model = None
    repair_method = None
    if repair_kind == "heuristic":
        repair_model = HeuristicRepairModel()
        repair_method = "heuristic"
    elif repair_kind == "hf":
        repair_model = HFCausalRepairModel(**repair_cfg.get("hf", generation_cfg.get("hf", {})))
        repair_method = "generic"
    elif repair_kind == "ollama":
        repair_model = OllamaRepairModel(**repair_cfg.get("ollama", {}))
        repair_method = "ollama"
    elif repair_kind == "none":
        repair_method = None

    timeout = args.timeout if args.timeout is not None else execution_cfg.get("timeout_seconds", 5.0)
    executor = SandboxedExecutor(
        timeout_seconds=float(timeout),
        memory_limit_mb=execution_cfg.get("memory_limit_mb"),
    )
    return DependencyGuardPipeline(
        generator=generator,
        repair_model=repair_model,
        executor=executor,
        enable_api_validation=bool(config.get("validation", {}).get("api", True)),
        enable_execution=bool(config.get("execution", {}).get("enabled", True)),
        repair_method=repair_method,
        repair_on_execution_error=bool(
            execution_cfg.get("repair_on_execution_error", True)
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
