from __future__ import annotations

import argparse
import json
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

    args = parser.parse_args(argv)
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
    if output_path in protected_paths:
        raise SystemExit("--output must not overwrite the source or test input file.")


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
