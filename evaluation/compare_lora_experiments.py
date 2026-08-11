from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_EXPERIMENTS = ["small_r4_e1", "full_r4_e1", "full_r8_e1"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default="results/controlled_api_repair_v2/lora_experiments"
    )
    parser.add_argument("--experiments", nargs="+", default=DEFAULT_EXPERIMENTS)
    parser.add_argument(
        "--output", default="results/controlled_api_repair_v2/lora_experiment_comparison"
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    rows = [load_experiment(root / name, name) for name in args.experiments]
    selected = max(
        rows,
        key=lambda row: (
            row["validation_unit_test_pass_rate"],
            -row["rank"],
            -row["validation_loss"],
        ),
    )
    payload = {
        "schema_version": 1,
        "selection_metric": "validation_unit_test_pass_rate",
        "selection_rule": (
            "Maximize validation unit-test pass rate; break ties with lower rank, "
            "then lower validation loss."
        ),
        "selected_experiment": selected["experiment"],
        "experiments": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def load_experiment(path: Path, name: str) -> dict[str, Any]:
    manifest = json.loads((path / "training_manifest.json").read_text(encoding="utf-8"))
    metrics = json.loads((path / "training_metrics.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (path / "validation" / "api_aware_lora_summary.json").read_text(encoding="utf-8")
    )
    config = manifest["config"]
    return {
        "experiment": name,
        "train_records": manifest["train_records"],
        "rank": config["lora"]["rank"],
        "alpha": config["lora"]["alpha"],
        "epochs": config["training"]["epochs"],
        "learning_rate": config["training"]["learning_rate"],
        "trainable_parameters": manifest["trainable_parameters"],
        "train_loss": metrics["train"]["train_loss"],
        "validation_loss": metrics["validation"]["eval_loss"],
        "train_truncated_records": manifest["sequence_lengths"]["train_truncated_records"],
        "validation_truncated_records": manifest["sequence_lengths"][
            "validation_truncated_records"
        ],
        "validation_task_count": summary["task_count"],
        "validation_syntax_valid_rate": summary["final_syntax_valid_rate"],
        "validation_execution_success_rate": summary["final_execution_success_rate"],
        "validation_unit_test_pass_rate": summary["unit_test_pass_rate"],
        "validation_repair_success_rate": summary["repair_success_rate"],
        "validation_repair_successes": summary["repair_successes"],
        "validation_repair_attempts": summary["repair_attempts"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
