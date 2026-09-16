from copy import deepcopy

import pytest

from evaluation.interview_metrics import (
    CHECKS,
    protocol_entered,
    real_pass,
    strict_rescue,
    summarize,
)


def evidence(version="2:bbb", passed=True):
    return {"host_status": "PASS" if passed else "FAIL", "candidate_version": version,
            "regression_guard": {"blocked": False}, "checks": {n: {"status": "success",
                "candidate_version": version, "evidence": {"passed": passed}} for n in CHECKS}}


def step(number, tool, version, passed=None):
    result = {"status": "success", "candidate_version": version,
              "evidence": {} if passed is None else {"passed": passed}}
    return {"step": number, "tool_call": {"name": tool, "arguments": {}}, "tool_result": result,
            "observation": deepcopy(result), "observed_steps": list(range(1,number))}


def paired():
    a = {"mode": "live", "attempted": True, "comparison_identity": "same", "cohort": "hard",
         "case_id": "example", "condition": "one-shot", "status": "FAIL", "repair_attempted": True,
         "unchanged": True, "candidate_version": "1:aaa", "final_verification": evidence("1:aaa", False)}
    b = {**a, "condition": "loop", "status": "PASS", "candidate_version": "2:bbb",
         "final_verification": evidence(), "capability_probe": {"status": "passed"},
         "trajectory": [step(1,"apply_patch","1:aaa"), step(2,"run_pytest","1:aaa",False),
                        step(3,"apply_patch","2:bbb"), step(4,"run_pytest","2:bbb",True),
                        step(5,"finish","2:bbb")]}
    b["trajectory"][-1]["tool_call"]["arguments"] = {"success": True}
    return a,b


def test_strict_rescue_exact_numerator_denominator():
    a,b = paired()
    detail = strict_rescue(a,b)
    assert detail["rescued"] and detail["eligible"] and detail["rescued_patch_step"] == 3
    summary = summarize([a,b])
    assert summary["strict_rescue"] == {"numerator":1,"denominator":1,"rate":1}
    assert summary["tool_protocol"]["numerator"] == 1


@pytest.mark.parametrize("change", ["one_shot_pass", "first_pass", "no_observation", "same_code",
                                    "mock", "tests_changed", "different_model", "scripted", "no_patch"])
def test_non_rescues(change):
    a,b = paired()
    if change == "one_shot_pass":
        a["status"] = "PASS"
    elif change == "first_pass":
        b["trajectory"][1]["tool_result"]["evidence"]["passed"] = True
    elif change == "no_observation":
        b["trajectory"][2]["observed_steps"] = []
    elif change == "same_code":
        b["trajectory"][2]["tool_result"]["candidate_version"] = "3:aaa"
    elif change == "mock":
        b["final_verification"]["checks"]["run_pytest"]["status"] = "mock"
    elif change == "tests_changed":
        b["unchanged"] = False
    elif change == "different_model":
        b["comparison_identity"] = "other"
    elif change == "scripted":
        a["mode"] = b["mode"] = "infrastructure"
    else:
        b["trajectory"] = []
    assert not strict_rescue(a,b)["rescued"]


def test_claimed_pass_without_host_evidence_and_stale_evidence():
    a,b = paired()
    b["final_verification"]["checks"]["execute"]["candidate_version"] = "old"
    assert not real_pass(b)
    assert summarize([a,b])["false_success"]["numerator"] == 1
    b["final_verification"] = {}
    assert not real_pass(b)


def test_probe_failure_is_in_protocol_denominator_but_not_rescue_denominator():
    a,b = paired()
    b.update(capability_probe={"status":"failed", "stage":"first_call", "reason":"text"}, trajectory=[])
    summary = summarize([a,b])
    assert not protocol_entered(b)
    assert summary["tool_protocol"] == {"numerator":0,"denominator":1,"rate":0}
    assert summary["strict_rescue"]["denominator"] == 0
    assert summary["probe_failures"] == {"first_call:text":1}


def test_control_modified_then_restored_is_not_preserved():
    _,b = paired()
    b.update(is_control=True, cohort="control", candidate_changed=False, patch_count=2)
    result = summarize([b])["conditions"]["loop"]["controls"]
    assert result["denominator"] == 1 and result["numerator"] == 0


def test_refusal_and_rollback_are_infrastructure_only_with_actual_hashes():
    rows = [{"condition":"infrastructure", "mode":"infrastructure", "expected_operations":[
        {"expected_code":"PATH_OUTSIDE_ROOT", "tool_result":{"status":"denied","evidence":{"error_code":"PATH_OUTSIDE_ROOT"}}},
        {"correctly_denied":True}], "rollback_required":True,
        "rollback":{"attempted":True,"succeeded":True}, "original_sha256":"original", "restored_sha256":"wrong"}]
    result = summarize(rows)
    assert result["infrastructure_only"]["unauthorized_refusal"]["rate"] == .5
    assert result["infrastructure_only"]["rollback"]["rate"] == 0
    assert result["strict_rescue"]["denominator"] == 0


def test_patch_rejection_categories():
    _,b = paired()
    b["trajectory"][0]["tool_result"].update(status="error", evidence={"error_code":"PATCH_CONTEXT_AMBIGUOUS"})
    result = summarize([b])
    assert result["patch_acceptance"]["rate"] == .5
    assert result["patch_failures"] == {"PATCH_CONTEXT_AMBIGUOUS":1}


def test_rescue_requires_native_finish_even_if_artifact_claims_pass():
    a, b = paired()
    b["trajectory"].pop()
    assert not strict_rescue(a, b)["rescued"]
    assert summarize([a, b])["capability_probe"] == {"numerator": 1, "denominator": 1, "rate": 1}
