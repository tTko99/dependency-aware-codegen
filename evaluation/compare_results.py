from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_METHODS = [
    "raw_base",
    "package_only_generic",
    "api_aware_generic",
    "api_aware_lora",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results/controlled_api_repair_v1")
    parser.add_argument("--methods", nargs="+", default=DEFAULT_METHODS)
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir)
    rows = [load_method(results_dir, method) for method in args.methods]
    payload = {"schema_version": 2, "methods": rows}
    (results_dir / "comparison.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    with (results_dir / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def load_method(results_dir: Path, method: str) -> dict[str, Any]:
    summary = json.loads((results_dir / f"{method}_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((results_dir / f"{method}_manifest.json").read_text(encoding="utf-8"))
    package = summary["package_detection"]
    api = summary["api_detection"]
    intervals = summary["confidence_intervals_95"]
    generation = manifest.get("repair_generation_config") or {}
    api_enabled = manifest["api_validation_enabled"]
    return {
        "method": method,
        "task_count": summary["task_count"],
        "package_true_positive": package["true_positive"],
        "package_false_positive": package["false_positive"],
        "package_false_negative": package["false_negative"],
        "package_precision": package["precision"],
        "package_recall": package["recall"],
        "package_f1": package["f1"],
        "api_detection_enabled": api_enabled,
        "api_true_positive": api["true_positive"] if api_enabled else None,
        "api_false_positive": api["false_positive"] if api_enabled else None,
        "api_false_negative": api["false_negative"] if api_enabled else None,
        "api_precision": api["precision"] if api_enabled else None,
        "api_recall": api["recall"] if api_enabled else None,
        "api_f1": api["f1"] if api_enabled else None,
        "initial_syntax_valid_rate": summary["initial_syntax_valid_rate"],
        "final_syntax_valid_rate": summary["final_syntax_valid_rate"],
        "final_syntax_valid_count": round(
            summary["final_syntax_valid_rate"] * summary["task_count"]
        ),
        "first_attempt_execution_success_rate": summary[
            "first_attempt_execution_success_rate"
        ],
        "final_execution_success_rate": summary["final_execution_success_rate"],
        "final_execution_successes": intervals["final_execution_success"]["successes"],
        "final_execution_ci_95_low": intervals["final_execution_success"]["low"],
        "final_execution_ci_95_high": intervals["final_execution_success"]["high"],
        "unit_test_pass_rate": summary["unit_test_pass_rate"],
        "unit_test_passes": intervals["unit_test_pass"]["successes"],
        "repair_attempt_rate": summary["repair_attempt_rate"],
        "repair_success_rate": summary["repair_success_rate"],
        "repair_attempts": summary["repair_attempts"],
        "repair_successes": summary["repair_successes"],
        "repair_success_ci_95_low": intervals["repair_success"]["low"],
        "repair_success_ci_95_high": intervals["repair_success"]["high"],
        "repair_required": summary["repair_required"],
        "overall_repair_success_rate": summary["overall_repair_success_rate"],
        "repair_model": manifest["repair_model"],
        "adapter_path": generation.get("adapter_path"),
        "dataset_sha256": manifest["dataset_sha256"],
        "config_sha256": manifest["config_sha256"],
        "resolved_config_sha256": manifest["resolved_config_sha256"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
