from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, help="Path to benchmark result JSON")
    parser.add_argument("--output", default=None, help="Optional output JSON path")
    args = parser.parse_args(argv)

    records = json.loads(Path(args.results).read_text(encoding="utf-8"))
    summary = analyze_failures(records)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def analyze_failures(records: list[dict[str, Any]]) -> dict[str, Any]:
    categories: Counter[str] = Counter()
    by_mutation: Counter[str] = Counter()
    cases: list[dict[str, Any]] = []
    for record in records:
        if record.get("final_execution_passed"):
            continue
        category = classify_final_failure(record)
        mutation_type = record.get("mutation_type") or "unknown"
        categories[category] += 1
        by_mutation[mutation_type] += 1
        cases.append(
            {
                "task_id": record.get("task_id"),
                "mutation_type": mutation_type,
                "category": category,
                "repair_attempted": record.get("repair_attempted", False),
                "initial_error": _error_summary(
                    record.get("pipeline", {}).get("execution_result")
                ),
                "final_error": _error_summary(
                    record.get("pipeline", {}).get("repaired_execution_result")
                ),
            }
        )
    return {
        "case_count": len(records),
        "failed_case_count": len(cases),
        "categories": dict(categories.most_common()),
        "failures_by_mutation": dict(by_mutation.most_common()),
        "cases": cases,
    }


def classify_final_failure(record: dict[str, Any]) -> str:
    pipeline = record.get("pipeline", {})
    if not record.get("repair_attempted"):
        return "repair_not_triggered"
    repaired_analysis = pipeline.get("repaired_analysis") or {}
    if repaired_analysis.get("syntax_error"):
        return "repaired_syntax_error"
    repaired_packages = pipeline.get("repaired_package_results", [])
    if any(not item.get("exists", False) for item in repaired_packages):
        return "unresolved_package"
    repaired_apis = pipeline.get("repaired_api_results", [])
    if any(not item.get("api_valid", False) for item in repaired_apis):
        return "unresolved_api"
    execution = pipeline.get("repaired_execution_result") or {}
    category = execution.get("error_category")
    if category and category != "unknown":
        return category
    stderr = execution.get("stderr") or execution.get("stdout", "")
    if "failed" in stderr.lower() or "assert" in stderr.lower():
        return "unit_test_failure"
    return "unknown"


def _error_summary(execution: dict[str, Any] | None) -> dict[str, Any] | None:
    if not execution:
        return None
    stderr = execution.get("stderr") or execution.get("stdout", "")
    return {
        "status": execution.get("status"),
        "error_type": execution.get("error_type"),
        "error_category": execution.get("error_category"),
        "stderr_tail": stderr[-500:] if stderr else "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
