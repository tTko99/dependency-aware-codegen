"""Prepare mixed-source tasks; no model calls before validated freeze."""

import argparse
import ast
import json
import time
from collections import Counter
from pathlib import Path

from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state, risk_findings
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save, verify_manifest
from scripts.horizontal_cases import authored_cases
from scripts.horizontal_sources import ROOT, immutable

DATA = ROOT.parent
CHECKS = ["validate_packages", "validate_apis", "execute", "run_pytest"]


def extract(version, module, name):
    path = ROOT / version / f"more_itertools/{module}.py.txt"
    text = path.read_text(encoding="utf-8")
    node = next(
        n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    lines = text.splitlines(keepends=True)
    # Preserve executable lines exactly; remove only a leading docstring.
    doc = node.body[0]
    if (
        isinstance(doc, ast.Expr)
        and isinstance(doc.value, ast.Constant)
        and isinstance(doc.value.value, str)
    ):
        return (
            "".join(
                lines[node.lineno - 1 : doc.lineno - 1] + lines[doc.end_lineno : node.end_lineno]
            )
            + "\n"
        )
    return ast.get_source_segment(text, node) + "\n"


def public_cases():
    specs = [
        (
            "partition",
            "recipes",
            "8.0.0",
            "8.1.0",
            "state",
            "Partition values into false and true groups. A None predicate means truth testing; mode even means an even-number predicate. Return two lists, preserving order.",
            "def solve(values, mode):\n    pred = None if mode is None else lambda x: x % 2 == 0\n    a, b = partition(pred, values)\n    return list(a), list(b)\n",
            [
                (([0, 1, False, 2], None), ([0, False], [1, 2])),
                (([1, 2, 3, 4], "even"), ([1, 3], [2, 4])),
                (([], None), ([], [])),
            ],
            [],
        ),
        (
            "split_before",
            "more",
            "8.7.0",
            "8.8.0",
            "data",
            "Split a sequence before each negative number, preserving order and all values. maxsplit limits splits; -1 is unlimited. Empty input yields no groups when maxsplit is not zero; maxsplit zero returns the unsplit sequence as one group.",
            "def solve(values, maxsplit):\n    return list(split_before(values, lambda x: x < 0, maxsplit=maxsplit))\n",
            [
                (([], -1), []),
                (([1, -2, 3, -4], -1), [[1], [-2, 3], [-4]]),
                (([-1, 2, -3, 4], 1), [[-1, 2], [-3, 4]]),
                (([], 0), [[]]),
            ],
            [],
        ),
        (
            "split_after",
            "more",
            "9.0.0",
            "9.1.0",
            "data",
            "Split a sequence after each zero. maxsplit limits splits, -1 is unlimited. Do not emit a trailing empty group when the last value ends the last allowed split; maxsplit zero returns one unsplit group.",
            "def solve(values, maxsplit):\n    return list(split_after(values, lambda x: x == 0, maxsplit=maxsplit))\n",
            [
                (([1, 0], 1), [[1, 0]]),
                (([1, 0, 2, 0, 3], 1), [[1, 0], [2, 0, 3]]),
                (([], -1), []),
                (([0, 0], -1), [[0], [0]]),
            ],
            [],
        ),
        (
            "zip_broadcast",
            "more",
            "8.10.0",
            "8.11.0",
            "data",
            "Zip input objects, broadcasting scalar numbers and strings across iterables. All scalars yield one tuple. strict=True must raise ValueError on unequal iterable lengths, regardless of argument order. No objects yields no tuples.",
            "def solve(objects, strict):\n    return list(zip_broadcast(*objects, strict=strict))\n",
            [
                (([[1, 2], "x"], True), [(1, "x"), (2, "x")]),
                (([2, "x"], True), [(2, "x")]),
                (([], True), []),
                (([[1, 2], [3]], False), [(1, 3)]),
            ],
            [(([[1, 2], [3]], True), "ValueError"), (([[1], [2, 3]], True), "ValueError")],
        ),
    ]
    prefix = (
        "from itertools import tee, repeat\nfrom operator import itemgetter\n"
        "_marker = object()\nUnequalIterablesError = ValueError\n"
        "def _zip_equal(*iterables):\n    return zip(*iterables, strict=True)\n\n"
    )
    result = []
    for name, module, old, new, category, requirement, wrapper, rows, errors in specs:
        archives = [
            json.loads((ROOT / v / "inventory.json").read_text(encoding="utf-8"))
            for v in (old, new)
        ]
        result.append(
            {
                "id": "public_" + name,
                "category": category,
                "requirement": requirement,
                "source": prefix + extract(old, module, name) + "\n" + wrapper,
                "reference": prefix + extract(new, module, name) + "\n" + wrapper,
                "rows": rows,
                "errors": errors,
                "extra_tests": "",
                "provenance": {
                    "kind": "public_defect_adaptation",
                    "production_bug": False,
                    "upstream_library_defect": True,
                    "project": "more-itertools",
                    "family": name,
                    "old_version": old,
                    "fixed_version": new,
                    "release_notes": archives[1]["release_notes"],
                    "source_archives": [
                        {"url": a["archive_url"], "sha256": a["archive_sha256"]} for a in archives
                    ],
                    "license": f"upstream/{old}/LICENSE.txt",
                    "adaptation": "Extract target function unchanged except removal of docstring. Add solve wrapper and explicit imports. For zip_broadcast use the same stdlib strict-zip helper and ValueError alias in both versions; test observable ValueError semantics. Tests authored from documented contract, not full upstream integration tests.",
                    "note": "split_after is the changed executable function; release notes call the fix maxsplit. These are adapted library defects, not full repository repairs.",
                },
            }
        )
    return result


def test_code(spec):
    text = "import pytest\nfrom solution import solve\n\n"
    text += "@pytest.mark.parametrize('args, expected', " + repr(spec["rows"]) + ")\n"
    text += "def test_contract(args, expected):\n    assert solve(*args) == expected\n"
    for index, (args, error) in enumerate(spec["errors"]):
        text += f"\ndef test_error_{index}():\n    with pytest.raises({error}):\n        solve(*{args!r})\n"
    return text + "\n" + spec["extra_tests"]


def prepare():
    if (DATA / "manifest.json").exists():
        raise ValueError("Already frozen; do not prepare again")
    for path in ROOT.glob("*/inventory.json"):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        for name, digest in metadata["files"].items():
            assert sha((path.parent / name).read_bytes()) == digest
    specs = authored_cases() + public_cases()
    controls = {s["id"] for s in specs if s["provenance"]["kind"] == "public_defect_adaptation"}
    for category in sorted({s["category"] for s in specs}):
        eligible = sorted(
            s["id"] for s in specs if s["category"] == category and s["id"].startswith("auth_")
        )
        controls.update(eligible[:2] if category == "api" else eligible[:1])
    screening, cases = [], []
    for spec in specs:
        tests = test_code(spec)
        risks = {
            label: risk_findings(code)
            for label, code in [
                ("source", spec["source"]),
                ("reference", spec["reference"]),
                ("tests", tests),
            ]
        }
        screening.append({"id": spec["id"], "risks": risks, "included": not any(risks.values())})
        if any(risks.values()):
            continue
        for control in [False, True] if spec["id"] in controls else [False]:
            name = spec["id"] + ("_control" if control else "")
            folder = DATA / "cases" / name
            files = {
                "input.py": spec["reference"] if control else spec["source"],
                "reference.py": spec["reference"],
                "test_input.py": tests,
                "requirement.txt": spec["requirement"],
            }
            for filename, text in files.items():
                # Pre-freeze preparation may be corrected, with screening/preflight retained.
                path = folder / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
            cases.append(
                {
                    "id": name,
                    "family": spec["id"],
                    "category": spec["category"],
                    "cohort": "control" if control else "hard",
                    "is_control": control,
                    "requirement": spec["requirement"],
                    "code_file": (folder / "input.py").as_posix(),
                    "test_file": (folder / "test_input.py").as_posix(),
                    "reference_file": (folder / "reference.py").as_posix(),
                    "hashes": {k: sha(v.encode()) for k, v in files.items()},
                    "required_checks": CHECKS,
                    "provenance": spec["provenance"],
                    "control_parent": spec["id"] if control else None,
                }
            )
    save(DATA / "screening.json", {"before_model_calls": True, "candidates": screening})
    save(
        DATA / "draft_manifest.json",
        {
            "name": "horizontal_mixed_v1",
            "cases": cases,
            "configs": {
                "configs/m7_qwen3_30b.json": sha(Path("configs/m7_qwen3_30b.json").read_bytes())
            },
            "source_groups": dict(
                Counter(c["provenance"]["kind"] for c in cases if not c["is_control"])
            ),
            "categories": dict(Counter(c["category"] for c in cases if not c["is_control"])),
            "limitations": [
                "Authored tasks are not production defects",
                "Public adaptations from one library",
                "Visible formal tests; no independent human acceptance",
                "Related controls do not enlarge defect denominator",
            ],
        },
    )
    immutable(DATA / "ruff.toml", b'exclude = ["cases", "upstream"]\n')
    print(
        f"Prepared {len(cases)} cases; {len(specs) - sum(s['included'] for s in screening)} screened out; not frozen"
    )


def validate():
    manifest = verify_manifest(DATA / "draft_manifest.json")
    records = []
    for case in manifest["cases"]:
        target = DATA / "preflight" / f"{case['id']}.json"
        if target.exists():
            prior = json.loads(target.read_text(encoding="utf-8"))
            if prior.get("input_hashes") == case["hashes"]:
                records.append(prior)
                continue
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
        check = evidence["initial"]["checks"]["run_pytest"]
        valid = evidence["reference"]["host_status"] == "PASS" and (
            evidence["initial"]["host_status"] == "PASS"
            if case["is_control"]
            else check["status"] == "success" and check["evidence"]["passed"] is False
        )
        record = {"case_id": case["id"], "input_hashes": case["hashes"], "valid": valid, **evidence}
        save(target, record)
        records.append(record)
        print(case["id"] + ": " + str(valid), flush=True)
    save(
        DATA / "preflight_summary.json",
        {
            "total": len(records),
            "valid": sum(r["valid"] for r in records),
            "invalid": [r["case_id"] for r in records if not r["valid"]],
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "validate"])
    args = parser.parse_args()
    prepare() if args.stage == "prepare" else validate()
