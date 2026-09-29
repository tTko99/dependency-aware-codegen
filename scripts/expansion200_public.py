"""Adapt public HumanEvalPack tests without altering their assertions."""

import json
from pathlib import Path

from depguard.agent.safety import risk_findings
from evaluation.interview_benchmark import save
from scripts.expansion200_sources import REVISION, ROOT


def public_specs():
    rows = json.loads((ROOT / "python_records.json").read_text(encoding="utf-8"))
    specs = []
    for row in sorted(rows, key=lambda r: int(r["task_id"].split("/")[1])):
        name = "hep_" + row["task_id"].split("/")[1].zfill(3)
        # Keep every upstream assertion and the original check invocation; add a pytest wrapper.
        tests = (
            "import random\nrandom.seed(42)\nfrom solution import "
            + row["entry_point"]
            + "\n"
            + row["test_setup"]
            + "\n"
            + row["test"]
            + "\n\ndef test_upstream_contract():\n    random.seed(42)\n    check("
            + row["entry_point"]
            + ")\n"
        )
        specs.append(
            {
                "id": name,
                "category": row["bug_type"].replace(" ", "_"),
                "requirement": "Repair the Python function according to this contract. Preserve its signature.\n"
                + row["instruction"],
                "source": row["prompt"] + row["buggy_solution"],
                "reference": row["prompt"] + row["canonical_solution"],
                "tests": tests,
                "provenance": {
                    "kind": "public_authored_bug_benchmark",
                    "production_bug": False,
                    "project": "HumanEvalPack",
                    "task_id": row["task_id"],
                    "family": row["entry_point"],
                    "revision": REVISION,
                    "url": f"https://huggingface.co/datasets/bigcode/humanevalpack/tree/{REVISION}",
                    "license": "MIT",
                    "method": "Upstream human-written bug; original prompt, buggy and canonical bodies retained; original assertions unchanged, pytest wrapper and deterministic random.seed(42) added; all upstream assertions retained.",
                    "failure_symptoms": row["failure_symptoms"],
                    "original_bug_type": row["bug_type"],
                },
            }
        )
    return specs


def screen():
    out = []
    for spec in public_specs():
        risks = {k: risk_findings(spec[k]) for k in ("source", "reference", "tests")}
        out.append({"id": spec["id"], "risks": risks, "eligible_static": not any(risks.values())})
    save(Path("data/expansion200_v1/public_screening.json"), out)
    print("Static eligibility", sum(r["eligible_static"] for r in out), "/", len(out))
    for r in out:
        if not r["eligible_static"]:
            print(r["id"], r["risks"])


if __name__ == "__main__":
    screen()
