"""Select before inference; no model outcome can affect inclusion."""

import json
from collections import Counter
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save
from scripts.expansion200_prepare import DATA, normalized


def main():
    if (DATA / "manifest.json").exists():
        raise ValueError("Already frozen")
    eligible = []
    decisions = []
    for case in json.loads((DATA / "public_draft.json").read_text(encoding="utf-8"))["cases"]:
        path = DATA / "preflight" / f"{case['id']}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        valid = record["valid"] and record["input_hashes"] == case["hashes"]
        key = sha(("expansion200-selection-v1:" + case["id"]).encode())
        decisions.append({"id": case["id"], "preflight_valid": valid, "selection_key": key})
        if valid:
            eligible.append((key, case))
    if len(eligible) < 100:
        raise ValueError("Fewer than 100 eligible public tasks; revise sourcing before inference")
    public = [c for _, c in sorted(eligible)[:100]]
    authored = json.loads((DATA / "authored_draft.json").read_text(encoding="utf-8"))["cases"]
    assert len(authored) == 31
    for c in authored:
        record = json.loads((DATA / "preflight" / f"{c['id']}.json").read_text(encoding="utf-8"))
        assert record["valid"] and record["input_hashes"] == c["hashes"], c["id"]
    cases = public + authored
    seen = {}
    collisions = []
    for manifest in [
        "data/external_eval_v1/manifest.json",
        "data/horizontal_eval_v1/manifest.json",
    ]:
        for c in json.loads(Path(manifest).read_text(encoding="utf-8"))["cases"]:
            if not c["is_control"]:
                seen[normalized(Path(c["code_file"]).read_text(encoding="utf-8"))] = c["id"]
    for c in cases:
        key = normalized(Path(c["code_file"]).read_text(encoding="utf-8"))
        if key in seen:
            collisions.append([seen[key], c["id"]])
        seen[key] = c["id"]
    save(
        DATA / "duplicate_audit.json",
        {
            "method": "AST without docstrings, locations or identifier spelling; attributes and literals retained. Not proof of semantic independence.",
            "collisions": collisions,
        },
    )
    if collisions:
        raise ValueError(collisions)
    ids = {c["id"] for c in public}
    for row in decisions:
        row["selected"] = row["id"] in ids
    save(
        DATA / "selection.json",
        {
            "policy": "100 eligible public tasks sorted by SHA256(expansion200-selection-v1:ID), plus 31 authored API contracts; no model inference used.",
            "public_eligible": len(eligible),
            "public_decisions": decisions,
        },
    )
    save(
        DATA / "draft_manifest.json",
        {
            "name": "expansion200_v1",
            "cases": cases,
            "configs": {
                "configs/m7_qwen3_30b.json": sha(Path("configs/m7_qwen3_30b.json").read_bytes())
            },
            "source_groups": dict(Counter(c["provenance"]["kind"] for c in cases)),
            "categories": dict(Counter(c["category"] for c in cases)),
            "limitations": [
                "Public HumanEvalPack has human-inserted bugs, not production failures.",
                "Known public benchmark may occur in pretraining; tests visible; no hidden human acceptance.",
                "Authored API cases are synthetic; similar concepts across sources are not independent production samples.",
            ],
        },
    )
    print("Selected 131 defective tasks before any model call")


if __name__ == "__main__":
    main()
