"""Verify extension provenance, fixed tests, selection and non-overlap before inference."""

import json
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import verify_manifest
from scripts.expansion200_prepare import DATA, normalized
from scripts.expansion200_public import public_specs
from scripts.horizontal_run import verify


def test_exact_defect_count_and_sources():
    cases = verify_manifest(DATA / "draft_manifest.json")["cases"]
    assert len(cases) == 131 and not any(c["is_control"] for c in cases)
    assert sum(c["provenance"]["kind"] == "public_authored_bug_benchmark" for c in cases) == 100
    assert sum(c["provenance"]["kind"] == "authored_api_scenario" for c in cases) == 31
    assert all(c["provenance"]["production_bug"] is False for c in cases)


def test_every_original_fails_and_reference_passes_with_matching_hashes():
    for c in verify_manifest(DATA / "draft_manifest.json")["cases"]:
        p = json.loads((DATA / "preflight" / f"{c['id']}.json").read_text(encoding="utf-8"))
        assert p["valid"] and p["input_hashes"] == c["hashes"]
        assert p["reference"]["host_status"] == "PASS"
        assert p["initial"]["checks"]["run_pytest"]["evidence"]["passed"] is False


def test_public_assertions_and_executable_bodies_preserved():
    records = json.loads(
        (DATA / "upstream/humanevalpack/python_records.json").read_text(encoding="utf-8")
    )
    by_id = {r["task_id"]: r for r in records}
    for s in public_specs():
        r = by_id[s["provenance"]["task_id"]]
        assert s["source"] == r["prompt"] + r["buggy_solution"]
        assert s["reference"] == r["prompt"] + r["canonical_solution"]
        assert r["test"] in s["tests"]
        assert "random.seed(42)" in s["tests"]


def test_selection_independent_of_model_outcomes():
    audit = json.loads((DATA / "selection.json").read_text(encoding="utf-8"))
    eligible = [r for r in audit["public_decisions"] if r["preflight_valid"]]
    expected = {r["id"] for r in sorted(eligible, key=lambda r: r["selection_key"])[:100]}
    actual = {r["id"] for r in audit["public_decisions"] if r["selected"]}
    assert expected == actual
    for r in eligible:
        assert r["selection_key"] == sha(("expansion200-selection-v1:" + r["id"]).encode())


def test_no_normalized_ast_duplicates_and_history_preserved():
    cases = verify_manifest(DATA / "draft_manifest.json")["cases"]
    keys = [normalized(Path(c["code_file"]).read_text(encoding="utf-8")) for c in cases]
    assert len(set(keys)) == 131
    assert (
        json.loads((DATA / "duplicate_audit.json").read_text(encoding="utf-8"))["collisions"] == []
    )
    verify()
