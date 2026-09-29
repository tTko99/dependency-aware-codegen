"""Horizontal evidence checks, kept outside the prior frozen implementation tree."""

import ast
import json

from evaluation.agent_benchmark import sha
from evaluation.external_validation import verify_freeze
from scripts.horizontal_cases import authored_cases
from scripts.horizontal_prepare import DATA, extract, public_cases
from scripts.horizontal_report import grouped


def test_explicit_provenance_and_family_uniqueness():
    authored = authored_cases()
    public = public_cases()
    assert len(authored) == 36 and len(public) == 4
    assert len({c["id"] for c in authored + public}) == 40
    assert all(c["provenance"]["production_bug"] is False for c in authored + public)
    assert all(c["provenance"]["kind"] == "authored_scenario" for c in authored)
    assert all(c["provenance"]["source_archives"] for c in public)


def test_extraction_changes_no_executable_target_code():
    from scripts.horizontal_sources import ROOT

    for version, name, module in [
        ("8.0.0", "partition", "recipes"),
        ("8.11.0", "zip_broadcast", "more"),
        ("9.1.0", "split_after", "more"),
    ]:
        text = (ROOT / version / f"more_itertools/{module}.py.txt").read_text(encoding="utf-8")
        original = next(
            n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        if isinstance(original.body[0], ast.Expr) and isinstance(
            original.body[0].value, ast.Constant
        ):
            original.body.pop(0)
        selected = ast.parse(extract(version, module, name)).body[0]
        assert ast.dump(original) == ast.dump(selected)


def test_all_manifest_hashes_and_preflight_match():
    manifest = json.loads((DATA / "draft_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["cases"]) == 50
    for case in manifest["cases"]:
        from pathlib import Path

        folder = Path(case["code_file"]).parent
        for name, digest in case["hashes"].items():
            assert sha((folder / name).read_bytes()) == digest
        row = json.loads((DATA / "preflight" / f"{case['id']}.json").read_text(encoding="utf-8"))
        assert row["valid"] and row["input_hashes"] == case["hashes"]


def test_group_denominators_do_not_pool_controls_or_sources():
    cases = [
        {"id": "a", "is_control": False, "kind": "public"},
        {"id": "b", "is_control": False, "kind": "authored"},
        {"id": "c", "is_control": True, "kind": "authored"},
    ]
    result = grouped(cases, [], lambda c: c["kind"])
    assert result["public"]["repair_cases"] == 1
    assert result["public"]["control_cases"] == 0
    assert result["authored"]["repair_cases"] == 1
    assert result["authored"]["control_cases"] == 1
    assert not result["public"]["complete"]


def test_historical_freeze_still_valid():
    verify_freeze()
