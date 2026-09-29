"""Reporting-only checks added after freeze; no Agent or evaluation changes."""
import copy
import json
from pathlib import Path

from evaluation.external_report import aggregate
from scripts.finalize_external_evidence import adjust


def fixture():
    root = Path("results/external_eval_v1/external")
    rows = [json.loads((root / name).read_text()) for name in (
        "one-shot_qb_levenshtein.json", "loop_qb_levenshtein.json",
        "one-shot_qb_bitcount.json", "loop_qb_bitcount.json")]
    cases = [{"id": name, "is_control": False} for name in ("qb_levenshtein", "qb_bitcount")]
    return {"cohorts": {"external": aggregate(cases, rows)}}, rows


def test_unknown_not_model_failure_or_zero_cost():
    summary, rows = fixture()
    result = adjust(summary, rows)["cohorts"]["external"]
    measured = next(r for r in rows if r["case_id"] == "qb_bitcount" and r["condition"] == "loop")
    assert result["conditions"]["loop"]["cost_repairs"]["runs"] == 1
    assert result["conditions"]["loop"]["cost_repairs"]["mean_seconds"] == measured["latency"]
    assert result["paired_repair_outcomes"]["interrupted_pair"] == 1
    assert not result["fully_observed"]
    assert result["observed_attempts"] == 3
    assert result["conditions"]["loop"]["repair_pass"]["denominator"] == 2
    assert result["conditions"]["loop"]["observed_repair_pass"]["denominator"] == 1


def test_original_summary_and_evidence_unmodified():
    summary, rows = fixture()
    before = copy.deepcopy((summary, rows))
    adjust(summary, rows)
    assert (summary, rows) == before


def test_complete_observation_preserves_costs_and_pair_outcomes():
    _, rows = fixture()
    rows = [r for r in rows if r["case_id"] == "qb_bitcount"]
    original = aggregate([{"id": "qb_bitcount", "is_control": False}], rows)
    result = adjust({"cohorts": {"external": original}}, rows)["cohorts"]["external"]
    assert result["fully_observed"]
    assert result["paired_repair_outcomes"] == original["paired_repair_outcomes"]
    assert result["conditions"]["loop"]["cost_repairs"] == original["conditions"]["loop"]["cost_repairs"]
