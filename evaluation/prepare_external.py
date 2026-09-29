"""Prepare and validate an external benchmark before any repair-model invocation."""
from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path

from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state, risk_findings
from evaluation.agent_benchmark import sha
from evaluation.external_sources import REVISION, ROOT
from evaluation.interview_benchmark import save

DATA = ROOT.parent
CONFIG = Path("configs/m7_qwen3_30b.json")
CHECKS = ["validate_packages", "validate_apis", "execute", "run_pytest"]


def immutable(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"Refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def upstream(relative):
    return (ROOT / (relative + ".txt")).read_bytes()


def test_rows(name):
    rows = [json.loads(line) for line in upstream(f"json_testcases/{name}.json").splitlines()
            if line.strip()]
    retained, omitted = [], []
    for index, (args, expected) in enumerate(rows):
        # Preserve the upstream pytest default exclusions; never omit for model outcome.
        slow = (name == "knapsack" and args[0] == 6404180) or (
            name == "levenshtein" and args == ["amanaplanacanalpanama",
                                               "docnoteidissentafastneverpreventsafatnessidietoncod"])
        if slow:
            omitted.append({"row": index, "reason": "upstream default slow-test exclusion"})
            continue
        if name == "hanoi":
            expected = [tuple(x) for x in expected]
        retained.append((args, expected))
    return retained, omitted


def tests_for(name, rows):
    expression = f"{name}(*input_data)"
    if name in {"flatten", "kheapsort"}:
        expression = f"list({expression})"
    expected = "pytest.approx(expected, abs=input_data[-1])" if name == "sqrt" else "expected"
    return (f"# Adapted from QuixBugs {REVISION}; see ../../upstream/LICENSE.txt\n"
            f"import pytest\nfrom solution import {name}\n\n"
            f"@pytest.mark.parametrize('input_data,expected', {rows!r})\n"
            f"def test_contract(input_data, expected):\n"
            f"    assert {expression} == {expected}\n")


def description(source, name):
    tree = ast.parse(source)
    docs = [n.value.value for n in tree.body if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)]
    return (f"Repair {name} to satisfy the following upstream contract and supplied tests. "
            "Preserve public function signatures and documented behavior.\n" + "\n".join(docs))


def prepare():
    if (DATA / "manifest.json").exists():
        raise FileExistsError("Already frozen; do not rebuild this version")
    inventory = json.loads((ROOT / "inventory.json").read_text())
    for name, expected in inventory["files"].items():
        if sha(upstream(name)) != expected:
            raise ValueError(f"Upstream evidence changed: {name}")
    selected, screening = [], []
    json_names = {p.name.removesuffix(".json.txt") for p in (ROOT / "json_testcases").iterdir()}
    for path in sorted((ROOT / "python_programs").glob("*.py.txt")):
        name = path.name.removesuffix(".py.txt")
        if name.endswith("_test") or name == "node":
            continue
        if name not in json_names:
            screening.append({"name": name, "included": False,
                              "reason": "graph/node fixtures outside single-file adapter scope"})
            continue
        source = upstream(f"python_programs/{name}.py").decode()
        reference = upstream(f"correct_python_programs/{name}.py").decode()
        rows, omitted = test_rows(name)
        tests = tests_for(name, rows)
        risks = {label: risk_findings(text) for label, text in
                 [("source", source), ("reference", reference), ("tests", tests)]}
        if any(risks.values()):
            screening.append({"name": name, "included": False,
                              "reason": "existing risk policy rejects source/reference/test",
                              "risk_findings": risks})
            continue
        selected.append((name, source, reference, tests, omitted, len(rows)))
        screening.append({"name": name, "included": True,
                          "reason": "self-contained; original and reference pass static screening",
                          "test_rows": len(rows), "omitted_rows": omitted})
    # Alphabetical fixed selection, BEFORE model outcomes; no outcome-based replacement.
    controls = {item[0] for item in selected[:10]}
    cases = []
    for name, source, reference, tests, omitted, count in selected:
        for control in ([False, True] if name in controls else [False]):
            case_id = "qb_" + name + ("_control" if control else "")
            folder = DATA / "cases" / case_id
            files = {"input.py": reference if control else source,
                     "reference.py": reference, "test_input.py": tests}
            requirement = description(source, name)
            files["requirement.txt"] = requirement
            for filename, text in files.items():
                immutable(folder / filename, text.encode())
            cases.append({"id": case_id, "family": name, "cohort": "control" if control else "hard",
                "is_control": control, "requirement": requirement,
                "code_file": (folder / "input.py").as_posix(),
                "test_file": (folder / "test_input.py").as_posix(),
                "reference_file": (folder / "reference.py").as_posix(),
                "hashes": {k: sha(v.encode()) for k, v in files.items()},
                "required_checks": CHECKS, "formal_test_count": count,
                "provenance": {"kind": "external_algorithm_benchmark_adaptation",
                    "repository": inventory["repository"], "revision": REVISION,
                    "source_url": f"{inventory['repository']}/blob/{REVISION}/python_programs/{name}.py",
                    "license": "MIT; upstream/LICENSE.txt", "production_bug": False,
                    "adaptation": "Source unchanged; embed upstream JSON tests with solution import. "
                                  "Retain upstream hanoi tuple / generator / sqrt tolerance semantics.",
                    "omitted_rows": omitted, "control_parent": "qb_" + name if control else None}})
    save(DATA / "screening.json", {"selection_before_model_calls": True,
        "candidates": screening, "repair_count": len(selected), "control_count": len(controls),
        "control_selection": "first ten statically eligible names alphabetically",
        "note": "Related controls are not independent repair families; not production defects."})
    save(DATA / "draft_manifest.json", {"schema_version": 1, "name": "external_quixbugs_v1",
        "cases": cases, "configs": {CONFIG.as_posix(): sha(CONFIG.read_bytes())},
        "role": "new external tasks; historical 15 are development-exposed regression only",
        "limitations": ["Public algorithms; training contamination unknown",
                        "All formal tests visible to both conditions; no hidden acceptance suite",
                        "Single benchmark and related controls; no population success-rate claim",
                        "Not real-user production defects or model-generated hallucinations"]})
    print(f"Prepared {len(selected)} repair tasks + {len(controls)} controls; NOT YET FROZEN")


def validate():
    from evaluation.interview_benchmark import verify_manifest
    manifest = verify_manifest(DATA / "draft_manifest.json")
    output = DATA / "preflight"
    for case in manifest["cases"]:
        path = output / (case["id"] + ".json")
        if path.exists():
            continue
        evidence = {}
        for label, source in [("initial", case["code_file"]), ("reference", case["reference_file"])]:
            state = load_state(source, case["test_file"], project_root=Path(source).parent,
                               execution_timeout_seconds=10,
                               validation_config={"required_checks": CHECKS})
            evidence[label] = validate_candidate(state, time.monotonic() + 60)
        # Initial bug must fail a REAL test, not merely be rejected by a policy.
        initial_test = evidence["initial"]["checks"]["run_pytest"]
        valid = evidence["reference"]["host_status"] == "PASS" and (
            evidence["initial"]["host_status"] == "PASS" if case["is_control"] else
            initial_test["status"] == "success" and initial_test["evidence"]["passed"] is False)
        save(path, {"case_id": case["id"], "valid": valid, **evidence})
        print(f"preflight {case['id']}: {'VALID' if valid else 'INVALID'}", flush=True)
    records = [json.loads((output / (c["id"] + ".json")).read_text()) for c in manifest["cases"]]
    save(DATA / "preflight_summary.json", {"count": len(records),
         "valid": sum(r["valid"] for r in records),
         "invalid": [r["case_id"] for r in records if not r["valid"]]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "validate"])
    args = parser.parse_args()
    prepare() if args.stage == "prepare" else validate()
