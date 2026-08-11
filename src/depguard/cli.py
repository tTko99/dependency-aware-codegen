from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from depguard.analysis import DependencyAnalyzer
from depguard.config import load_config
from depguard.execution import SandboxedExecutor
from depguard.models.hf import HFCausalCodeGenerator, HFCausalRepairModel
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
    run_parser.add_argument("--repair", choices=["none", "hf", "heuristic"], default=None)
    run_parser.add_argument("--timeout", type=float, default=None)
    _add_code_args(run_parser)

    args = parser.parse_args(argv)
    if args.command == "analyze":
        code = _read_code(args)
        result = DependencyAnalyzer().analyze(code)
        print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        config = load_config(args.config)
        code = _read_code(args, required=False)
        pipeline = _build_pipeline(config, args)
        result = pipeline.run(requirement=args.requirement, code=code)
        payload = to_jsonable(result)
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


def _build_pipeline(config: dict[str, Any], args: argparse.Namespace) -> DependencyGuardPipeline:
    generation_cfg = config.get("generation", {})
    repair_cfg = config.get("repair", {})
    execution_cfg = config.get("execution", {})

    code_provided = bool(getattr(args, "code", None) or getattr(args, "code_file", None))
    generator_kind = args.generator or generation_cfg.get("kind")
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
