from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.failure_analysis import classify_final_failure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    records = json.loads(Path(args.results).read_text(encoding="utf-8"))
    diagnosis = diagnose(records)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(diagnosis, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(diagnosis, indent=2, sort_keys=True))
    return 0


def diagnose(records: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [record for record in records if record.get("repair_attempted")]
    counters: Counter[str] = Counter()
    by_mutation: dict[str, Counter[str]] = defaultdict(Counter)
    cases: list[dict[str, Any]] = []
    for record in attempted:
        pipeline = record["pipeline"]
        original = pipeline.get("generated_code") or ""
        repaired = pipeline.get("repaired_code") or ""
        target = record.get("target") or ""
        features = {
            "execution_passed": bool(record.get("final_execution_passed")),
            "unchanged": normalized_code(original) == normalized_code(repaired),
            "exact_target": normalized_code(target) == normalized_code(repaired),
            "syntax_valid": is_syntax_valid(repaired),
            "contains_markdown_fence": "```" in repaired,
            "longer_than_2x_input": len(repaired) > 2 * max(1, len(original)),
        }
        mutation_type = record.get("mutation_type") or "unknown"
        for feature, enabled in features.items():
            if enabled:
                counters[feature] += 1
                by_mutation[mutation_type][feature] += 1
        if not features["execution_passed"]:
            failure = classify_final_failure(record)
            counters[f"failure:{failure}"] += 1
            by_mutation[mutation_type][f"failure:{failure}"] += 1
            cases.append(
                {
                    "task_id": record.get("task_id"),
                    "leakage_group": record.get("leakage_group"),
                    "mutation_type": mutation_type,
                    "failure": failure,
                    **features,
                }
            )
    return {
        "case_count": len(records),
        "repair_attempt_count": len(attempted),
        "counts": dict(sorted(counters.items())),
        "by_mutation_type": {
            key: dict(sorted(value.items())) for key, value in sorted(by_mutation.items())
        },
        "failed_cases": cases,
    }


def normalized_code(code: str) -> str:
    try:
        return ast.dump(ast.parse(code), include_attributes=False)
    except SyntaxError:
        return code.strip()


def is_syntax_valid(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
