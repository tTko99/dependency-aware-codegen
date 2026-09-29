"""Integrity and denominator tests for the independent external comparison."""
import copy

import pytest

from evaluation.agent_benchmark import sha
from evaluation.external_report import aggregate
from evaluation.external_validation import identity, verify_hashes
from evaluation.prepare_external import immutable
from evaluation.prepare_external import test_rows as upstream_rows
from evaluation.prepare_external import tests_for as make_tests


def row(name, condition, control=False, status="PASS"):
    return {"case_id": name, "condition": condition, "cohort": "control" if control else "hard",
        "is_control": control, "mode": "live", "attempted": True, "status": status,
        "termination_reason": "finish", "candidate_version": "1:abc", "unchanged": True,
        "required_checks": ["run_pytest"], "patch_count": 0 if control else 1,
        "candidate_changed": not control, "model_calls": 0 if control else 4,
        "agent_invoked": not control, "trajectory": [], "latency": 1,
        "final_verification": {"host_status": "PASS", "candidate_version": "1:abc",
            "checks": {"run_pytest": {"status": "success", "candidate_version": "1:abc",
                                      "evidence": {"passed": True}}}}}


def test_controls_do_not_inflate_repair_denominator():
    cases = [{"id": "bug", "is_control": False}, {"id": "correct", "is_control": True}]
    rows = [row("bug", c, status="ERROR") for c in ("one-shot", "loop")]
    rows += [row("correct", c, True) for c in ("one-shot", "loop")]
    result = aggregate(cases, rows)
    assert result["conditions"]["loop"]["repair_pass"]["rate"] == 0
    assert result["conditions"]["loop"]["all_pass"]["rate"] == .5
    assert result["conditions"]["loop"]["controls_preserved"]["rate"] == 1
    assert result["tool_protocol"]["denominator"] == 1


def test_missing_attempt_stays_in_planned_denominator():
    cases = [{"id": "a", "is_control": False}, {"id": "b", "is_control": False}]
    result = aggregate(cases, [row("a", "loop")])
    assert not result["complete"]
    assert result["conditions"]["loop"]["repair_pass"]["denominator"] == 2
    assert len(result["missing_attempts"]) == 3


def test_duplicate_or_unknown_results_cannot_be_selected():
    cases = [{"id": "a", "is_control": False}]
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate(cases, [row("a", "loop"), row("a", "loop")])
    with pytest.raises(ValueError, match="Unexpected"):
        aggregate(cases, [row("other", "loop")])


@pytest.mark.parametrize("tamper", ["mock", "stale", "inputs"])
def test_invalid_evidence_never_counts_pass(tamper):
    value = row("a", "loop")
    if tamper == "mock":
        value["final_verification"]["checks"]["run_pytest"]["status"] = "mock"
    elif tamper == "stale":
        value["final_verification"]["checks"]["run_pytest"]["candidate_version"] = "0:old"
    else:
        value["unchanged"] = False
    result = aggregate([{"id": "a", "is_control": False}], [value])
    assert result["conditions"]["loop"]["repair_pass"]["numerator"] == 0


def test_control_model_invocation_not_preserved():
    value = row("c", "loop", control=True)
    value["model_calls"] = 1
    result = aggregate([{"id": "c", "is_control": True}], [value])
    assert result["conditions"]["loop"]["controls_preserved"]["numerator"] == 0


def test_false_finish_recovered_not_final_false_success():
    value = row("a", "loop")
    value["trajectory"] = [{"tool_call": {"name": "finish", "arguments": {"outcome": "success"}},
                            "tool_result": {"status": "error"}}]
    value["rejected_finish_count"] = 1
    result = aggregate([{"id": "a", "is_control": False}], [value])
    assert result["false_success_all_tasks"]["numerator"] == 0
    failed = copy.deepcopy(value)
    failed["status"] = "FAIL"
    result = aggregate([{"id": "a", "is_control": False}], [failed])
    assert result["false_success_all_tasks"]["numerator"] == 1


def test_frozen_file_changes_detected(tmp_path):
    path = tmp_path / "source.txt"
    immutable(path, b"original")
    expected = {path.as_posix(): sha(b"original")}
    verify_hashes(expected)
    with pytest.raises(ValueError, match="overwrite"):
        immutable(path, b"changed")
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_hashes(expected)


def test_identity_requires_actual_digest():
    with pytest.raises(ValueError):
        identity({"installed_model": {"name": "qwen3-coder:30b"}})


def test_adapter_retains_upstream_oracles():
    rows, omitted = upstream_rows("hanoi")
    assert isinstance(rows[1][1][0], tuple)
    assert not omitted
    assert "list(flatten(*input_data))" in make_tests("flatten", [])
    assert "pytest.approx" in make_tests("sqrt", [])
    _, omitted = upstream_rows("knapsack")
    assert len(omitted) == 1
    _, omitted = upstream_rows("levenshtein")
    assert len(omitted) == 1
