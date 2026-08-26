from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from depguard.config import load_config
from depguard.execution import SandboxedExecutor
from depguard.models.hf import HFCausalCodeGenerator, HFCausalRepairModel
from depguard.models.ollama import OllamaError, OllamaRepairModel
from depguard.pipeline import DependencyGuardPipeline
from depguard.schemas import ErrorCategory, PipelineResult, to_jsonable
from depguard.utils.jsonl import read_jsonl
from evaluation.metrics import aggregate_detection, rate, wilson_interval

METHODS = {
    "raw_base",
    "api_detector_only",
    "package_only_generic",
    "api_aware_generic",
    "api_aware_lora",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/evaluation.yaml")
    parser.add_argument("--method", choices=sorted(METHODS), default="api_aware_generic")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--task-id", action="append", default=None)
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--adapter-path", default=None)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = load_config(config_path)
    if args.dataset_path:
        config["benchmark"]["dataset_path"] = args.dataset_path
    if args.output_dir:
        config["benchmark"]["output_dir"] = args.output_dir
    if args.adapter_path:
        config["repair"]["lora_adapter_path"] = args.adapter_path
    dataset_path = Path(config["benchmark"]["dataset_path"])
    output_dir = Path(config["benchmark"].get("output_dir", "results"))
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = read_jsonl(dataset_path)
    if args.task_id:
        requested_ids = set(args.task_id)
        available_ids = {task.get("id") for task in tasks}
        missing_ids = sorted(requested_ids - available_ids)
        if missing_ids:
            raise ValueError(f"Unknown benchmark task IDs: {', '.join(missing_ids)}")
        tasks = [task for task in tasks if task.get("id") in requested_ids]
    if args.limit is not None:
        tasks = tasks[: args.limit]

    pipeline = build_pipeline(config, args.method)
    records: list[dict[str, Any]] = []
    started = time.time()
    for index, task in enumerate(tasks, start=1):
        if pipeline.repair_model is not None and hasattr(
            pipeline.repair_model, "last_response_metadata"
        ):
            pipeline.repair_model.last_response_metadata = {}
        code = None if config["benchmark"].get("generate", False) else task.get("code", task.get("buggy_code"))
        result = pipeline.run(
            requirement=task["requirement"],
            code=code,
            test_code=task.get("test_code"),
        )
        record = record_from_result(task, result, args.method)
        response_metadata = getattr(
            pipeline.repair_model, "last_response_metadata", None
        )
        if record["repair_attempted"] and response_metadata:
            record["repair_backend_metadata"] = dict(response_metadata)
        records.append(record)
        print(f"[{index}/{len(tasks)}] {task.get('id')}: {records[-1]['final_execution_passed']}")

    summary = summarize_records(records)
    summary["repair_latency_seconds"] = summarize_repair_latency(records)
    manifest = experiment_manifest(
        config=config,
        config_path=config_path,
        dataset_path=dataset_path,
        method=args.method,
        pipeline=pipeline,
        wall_time_seconds=time.time() - started,
        task_ids=[record["task_id"] for record in records],
        requested_task_ids=args.task_id,
        limit=args.limit,
    )
    result_path = output_dir / f"{args.method}.json"
    summary_json_path = output_dir / f"{args.method}_summary.json"
    summary_csv_path = output_dir / f"{args.method}_summary.csv"
    manifest_path = output_dir / f"{args.method}_manifest.json"
    resolved_config_path = output_dir / f"{args.method}_resolved_config.json"
    result_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    resolved_config_path.write_text(
        json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_summary_csv(summary_csv_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def build_pipeline(config: dict[str, Any], method: str) -> DependencyGuardPipeline:
    generation_cfg = config.get("generation", {})
    repair_cfg = config.get("repair", {})
    execution_cfg = config.get("execution", {})
    benchmark_cfg = config.get("benchmark", {})

    generator = None
    if benchmark_cfg.get("generate", False):
        generator = HFCausalCodeGenerator(**generation_cfg["hf"])

    enable_api = method in {"api_detector_only", "api_aware_generic", "api_aware_lora"}
    repair_model = None
    repair_method = None
    if method in {"package_only_generic", "api_aware_generic"}:
        repair_kind = repair_cfg.get("kind", "hf")
        if repair_kind == "hf":
            repair_model = HFCausalRepairModel(**repair_cfg["hf"])
            repair_method = "generic"
        elif repair_kind == "ollama":
            repair_model = OllamaRepairModel(**repair_cfg["ollama"])
            repair_method = "ollama"
        else:
            raise ValueError(f"Unsupported repair backend kind: {repair_kind}")
    elif method == "api_aware_lora":
        adapter_path = repair_cfg.get("lora_adapter_path")
        if not adapter_path:
            raise ValueError("LoRA methods require repair.lora_adapter_path in the config")
        hf_cfg = dict(repair_cfg["hf"])
        hf_cfg["adapter_path"] = adapter_path
        repair_model = HFCausalRepairModel(**hf_cfg)
        repair_method = "lora"

    return DependencyGuardPipeline(
        generator=generator,
        repair_model=repair_model,
        executor=SandboxedExecutor(
            timeout_seconds=float(execution_cfg.get("timeout_seconds", 5.0)),
            memory_limit_mb=execution_cfg.get("memory_limit_mb"),
        ),
        enable_api_validation=enable_api,
        enable_execution=bool(execution_cfg.get("enabled", True)),
        repair_method=repair_method,
        repair_on_execution_error=bool(execution_cfg.get("repair_on_execution_error", False)),
    )


def record_from_result(
    task: dict[str, Any], result: PipelineResult, method: str
) -> dict[str, Any]:
    observed_invalid_packages = [
        package.package for package in result.package_results if not package.exists
    ]
    observed_invalid_apis = [
        api.reference.canonical_path
        for api in result.api_results
        if not api.api_valid and api.status != ErrorCategory.HALLUCINATED_PACKAGE.value
    ]
    initial_passed = bool(result.execution_result and result.execution_result.status == "passed")
    repaired_passed = bool(
        result.repaired_execution_result and result.repaired_execution_result.status == "passed"
    )
    final_passed = repaired_passed if result.repaired_code is not None else initial_passed
    final_analysis = result.repaired_analysis or result.analysis
    return {
        "task_id": task.get("id"),
        "leakage_group": task.get("leakage_group", task.get("id")),
        "method": method,
        "requirement": task["requirement"],
        "mutation_type": task.get("metadata", {}).get("mutation_type"),
        "original_api": task.get("metadata", {}).get("original_api"),
        "expected_invalid_packages": task.get("expected_invalid_packages", []),
        "expected_invalid_apis": task.get("expected_invalid_apis", []),
        "observed_invalid_packages": observed_invalid_packages,
        "observed_invalid_apis": observed_invalid_apis,
        "initial_syntax_valid": result.analysis.syntax_error is None,
        "final_syntax_valid": final_analysis.syntax_error is None,
        "execution_passed": initial_passed,
        "post_repair_passed": repaired_passed,
        "final_execution_passed": final_passed,
        "unit_test_available": bool(task.get("test_code")),
        "unit_test_passed": final_passed if task.get("test_code") else None,
        "repair_required": not initial_passed,
        "repair_attempted": result.repaired_code is not None,
        "repair_success": bool(not initial_passed and result.repaired_code is not None and final_passed),
        "target": task.get("target"),
        "pipeline": to_jsonable(result),
    }


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    repair_attempts = sum(1 for record in records if record["repair_attempted"])
    repair_required = sum(1 for record in records if record["repair_required"])
    repair_successes = sum(1 for record in records if record["repair_success"])
    unit_test_records = [record for record in records if record["unit_test_available"]]
    final_successes = sum(1 for record in records if record["final_execution_passed"])
    unit_successes = sum(1 for record in unit_test_records if record["unit_test_passed"])
    initial_syntax_valid = sum(1 for record in records if record["initial_syntax_valid"])
    final_syntax_valid = sum(1 for record in records if record["final_syntax_valid"])
    valid_controls = [
        record for record in records if record.get("mutation_type") == "valid_control"
    ]
    preserved_controls = sum(
        1 for record in valid_controls if record["final_execution_passed"]
    )
    unnecessary_control_repairs = sum(
        1 for record in valid_controls if record["repair_attempted"]
    )
    by_mutation: dict[str, Any] = {}
    for mutation_type in sorted({record.get("mutation_type") or "unknown" for record in records}):
        category_records = [
            record for record in records if (record.get("mutation_type") or "unknown") == mutation_type
        ]
        category_successes = sum(
            1 for record in category_records if record["final_execution_passed"]
        )
        by_mutation[mutation_type] = {
            "count": len(category_records),
            "final_execution_successes": category_successes,
            "final_execution_success_rate": rate(category_successes, len(category_records)),
            "final_execution_success_wilson_95": wilson_interval(
                category_successes, len(category_records)
            ),
        }
    return {
        "task_count": total,
        "package_detection": aggregate_detection(records, "packages"),
        "api_detection": aggregate_detection(records, "apis"),
        "initial_syntax_valid_count": initial_syntax_valid,
        "initial_syntax_valid_rate": rate(initial_syntax_valid, total),
        "final_syntax_valid_count": final_syntax_valid,
        "final_syntax_valid_rate": rate(final_syntax_valid, total),
        "first_attempt_execution_success_rate": rate(
            sum(1 for record in records if record["execution_passed"]), total
        ),
        "final_execution_success_rate": rate(final_successes, total),
        "unit_test_pass_rate": rate(unit_successes, len(unit_test_records)),
        "repair_attempt_rate": rate(repair_attempts, repair_required),
        "repair_success_rate": rate(repair_successes, repair_attempts),
        "overall_repair_success_rate": rate(repair_successes, repair_required),
        "repair_attempts": repair_attempts,
        "repair_required": repair_required,
        "detector_misses": repair_required - repair_attempts,
        "repair_successes": repair_successes,
        "valid_controls": {
            "count": len(valid_controls),
            "preserved": preserved_controls,
            "unnecessary_repair_attempts": unnecessary_control_repairs,
        },
        "confidence_intervals_95": {
            "final_execution_success": wilson_interval(final_successes, total),
            "unit_test_pass": wilson_interval(unit_successes, len(unit_test_records)),
            "repair_success": wilson_interval(repair_successes, repair_attempts),
        },
        "by_mutation_type": by_mutation,
    }


def summarize_repair_latency(records: list[dict[str, Any]]) -> dict[str, Any]:
    backend_seconds = [
        metadata["total_duration"] / 1_000_000_000
        for record in records
        if isinstance((metadata := record.get("repair_backend_metadata")), dict)
        and isinstance(metadata.get("total_duration"), (int, float))
    ]
    pipeline_seconds = [
        record["pipeline"]["latency_seconds"]
        for record in records
        if record["repair_attempted"]
        and isinstance(record.get("pipeline"), dict)
        and isinstance(record["pipeline"].get("latency_seconds"), (int, float))
    ]
    return {
        "backend_total_duration": descriptive_latency(backend_seconds),
        "pipeline_attempted_rows": descriptive_latency(pipeline_seconds),
    }


def descriptive_latency(values: list[float]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None}
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


def experiment_manifest(
    *,
    config: dict[str, Any],
    config_path: Path,
    dataset_path: Path,
    method: str,
    pipeline: DependencyGuardPipeline,
    wall_time_seconds: float,
    task_ids: list[str | None],
    requested_task_ids: list[str] | None,
    limit: int | None,
) -> dict[str, Any]:
    repair_model = pipeline.repair_model
    backend_metadata = None
    metadata_loader = getattr(repair_model, "runtime_metadata", None)
    if callable(metadata_loader):
        try:
            backend_metadata = metadata_loader()
        except OllamaError as exc:
            backend_metadata = {"metadata_error": f"{type(exc).__name__}: {exc}"}
    return {
        "schema_version": 2,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "benchmark": config.get("benchmark", {}).get("name"),
        "method": method,
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "resolved_config_sha256": hashlib.sha256(
            json.dumps(config, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "resolved_config": config,
        "dataset_path": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "python_version": platform.python_version(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_executable": sys.executable,
        },
        "library_versions": {
            package: version(package)
            for package in ("torch", "transformers", "peft", "datasets", "accelerate")
        },
        "repair_model": getattr(repair_model, "model_name", None),
        "repair_generation_config": getattr(repair_model, "generation_config", None),
        "repair_backend_metadata": backend_metadata,
        "generator_loaded": pipeline.generator is not None,
        "api_validation_enabled": pipeline.enable_api_validation,
        "repair_on_execution_error": pipeline.repair_on_execution_error,
        "task_selection": {
            "evaluated_task_count": len(task_ids),
            "evaluated_task_ids": task_ids,
            "requested_task_ids": requested_task_ids,
            "limit": limit,
        },
        "wall_time_seconds": wall_time_seconds,
    }


def write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    rows = []
    for key, value in summary.items():
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                rows.append({"metric": f"{key}.{nested_key}", "value": nested_value})
        else:
            rows.append({"metric": key, "value": value})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
