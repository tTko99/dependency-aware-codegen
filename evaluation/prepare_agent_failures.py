"""Freeze all five historical *attempted* 7B one-shot failures, without selection by loop outcome."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = Path("results/controlled_api_repair_7b_ollama/test/api_aware_generic.json")
    catalog = Path("data/raw/expanded_api_examples.jsonl")
    rows = json.loads(source.read_text(encoding="utf-8"))
    originals = {row["id"]: row for row in (
        json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines()
    )}
    selected = [row for row in rows if row["repair_attempted"] and not row["post_repair_passed"]]
    root = Path("data/agent_failures")
    cases = []
    for row in selected:
        folder = root / "cases" / row["task_id"]
        folder.mkdir(parents=True, exist_ok=True)
        values = {"input.py": row["pipeline"]["generated_code"],
                  "test_input.py": originals[row["task_id"]]["test_code"],
                  "historical_repair.py": row["pipeline"]["repaired_code"],
                  "reference.py": row["target"]}
        hashes = {}
        for name, text in values.items():
            file = folder / name
            file.write_bytes(text.encode("utf-8"))
            hashes[name] = digest(file)
        cases.append({
            "id": row["task_id"], "requirement": row["requirement"],
            "code_file": (folder / "input.py").as_posix(),
            "test_file": (folder / "test_input.py").as_posix(),
            "historical_repair_file": (folder / "historical_repair.py").as_posix(),
            "reference_file": (folder / "reference.py").as_posix(), "hashes": hashes,
            "provenance": {"kind": "historical_observed_one_shot_failure",
                           "artifact": source.as_posix(), "task_id": row["task_id"],
                           "catalog": catalog.as_posix(),
                           "historical_repair_attempted": True,
                           "historical_post_repair_passed": False},
        })
    manifest = {
        "schema_version": 1,
        "selection": "All historical attempted failures; excludes detector misses and controls",
        "claim_scope": "Historical failure cohort, not guaranteed to fail a new one-shot run",
        "source_artifact_sha256": digest(source), "source_catalog_sha256": digest(catalog),
        "comparison_config": "configs/agent_evaluation.json",
        "comparison_config_sha256": digest(Path("configs/agent_evaluation.json")),
        "cases": cases,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
