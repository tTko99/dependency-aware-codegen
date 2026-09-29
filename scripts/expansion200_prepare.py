"""Preparation and immutable-input checks for the 131-task extension."""

import argparse
import ast
import json
import time
from pathlib import Path

from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state, risk_findings
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save, verify_manifest
from scripts.expansion200_public import public_specs
from scripts.horizontal_prepare import CHECKS
from scripts.horizontal_run import verify as verify_previous

DATA = Path("data/expansion200_v1")


def normalized(code):
    tree = ast.parse(code)
    names = {}
    for node in ast.walk(tree):
        if hasattr(node, "body") and isinstance(node.body, list):
            node.body[:] = [
                n
                for n in node.body
                if not (
                    isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str)
                )
            ]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.setdefault(node.name, "v" + str(len(names)))
            node.name = names[node.name]
        elif isinstance(node, ast.Name):
            names.setdefault(node.id, "v" + str(len(names)))
            node.id = names[node.id]
        elif isinstance(node, ast.arg):
            names.setdefault(node.arg, "v" + str(len(names)))
            node.arg = names[node.arg]
    return sha(ast.dump(tree, include_attributes=False).encode())


def prepare_public():
    verify_previous()
    if (DATA / "manifest.json").exists():
        raise ValueError("Already frozen")
    history = set()
    for path in ["data/external_eval_v1/manifest.json", "data/horizontal_eval_v1/manifest.json"]:
        for c in json.loads(Path(path).read_text(encoding="utf-8"))["cases"]:
            history.add(normalized(Path(c["code_file"]).read_text(encoding="utf-8")))
    screened = []
    cases = []
    for spec in public_specs():
        risks = {k: risk_findings(spec[k]) for k in ("source", "reference", "tests")}
        duplicate = normalized(spec["source"]) in history
        eligible = not any(risks.values()) and not duplicate
        screened.append(
            {"id": spec["id"], "risks": risks, "duplicate_history": duplicate, "eligible": eligible}
        )
        if eligible:
            cases.append(materialize(spec))
    save(DATA / "public_screening.json", screened)
    save(DATA / "public_draft.json", {"cases": cases, "configs": {}})
    (DATA / "ruff.toml").write_text('exclude = ["cases", "upstream"]\n', encoding="utf-8")
    print("Public candidates prepared:", len(cases), flush=True)


def materialize(spec):
    folder = DATA / "cases" / spec["id"]
    files = {
        "input.py": spec["source"],
        "reference.py": spec["reference"],
        "test_input.py": spec["tests"],
        "requirement.txt": spec["requirement"],
    }
    for name, text in files.items():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    return {
        "id": spec["id"],
        "family": spec["provenance"]["family"],
        "category": spec["category"],
        "cohort": "hard",
        "is_control": False,
        "requirement": spec["requirement"],
        "code_file": (folder / "input.py").as_posix(),
        "test_file": (folder / "test_input.py").as_posix(),
        "reference_file": (folder / "reference.py").as_posix(),
        "hashes": {k: sha(v.encode()) for k, v in files.items()},
        "required_checks": CHECKS,
        "provenance": spec["provenance"],
        "control_parent": None,
    }


def validate(path):
    if (DATA / "manifest.json").exists():
        raise ValueError("Cannot overwrite frozen preflight")
    manifest = verify_manifest(DATA / path)
    records = []
    for case in manifest["cases"]:
        target = DATA / "preflight" / f"{case['id']}.json"
        if target.exists():
            prior = json.loads(target.read_text(encoding="utf-8"))
            if prior["input_hashes"] == case["hashes"]:
                records.append(prior)
                continue
            archive = DATA / "preflight_history" / f"{case['id']}_{sha(target.read_bytes())}.json"
            archive.parent.mkdir(exist_ok=True)
            archive.write_bytes(target.read_bytes())
        evidence = {}
        for label, key in [("initial", "code_file"), ("reference", "reference_file")]:
            state = load_state(
                case[key],
                case["test_file"],
                project_root=Path(case[key]).parent,
                execution_timeout_seconds=10,
                validation_config={"required_checks": CHECKS},
            )
            evidence[label] = validate_candidate(state, time.monotonic() + 60)
        check = evidence["initial"]["checks"].get("run_pytest", {})
        valid = (
            evidence["reference"]["host_status"] == "PASS"
            and check.get("status") == "success"
            and check.get("evidence", {}).get("passed") is False
        )
        record = {"case_id": case["id"], "input_hashes": case["hashes"], "valid": valid, **evidence}
        save(target, record)
        records.append(record)
        print(case["id"], valid, flush=True)
    save(
        DATA / (path.replace(".json", "_preflight_summary.json")),
        {
            "total": len(records),
            "valid": sum(r["valid"] for r in records),
            "invalid": [r["case_id"] for r in records if not r["valid"]],
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["public", "validate"])
    parser.add_argument("--manifest", default="public_draft.json")
    args = parser.parse_args()
    prepare_public() if args.stage == "public" else validate(args.manifest)
