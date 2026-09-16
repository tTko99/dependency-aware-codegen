import hashlib
import json
from pathlib import Path

from evaluation.agent_benchmark import rescue_details


def test_failure_cohort_is_frozen_and_excludes_unattempted_cases():
    manifest = json.loads(Path("data/agent_failures/manifest.json").read_text())
    assert len(manifest["cases"]) == 5
    for case in manifest["cases"]:
        assert case["provenance"]["historical_repair_attempted"] is True
        assert case["provenance"]["historical_post_repair_passed"] is False
        folder = Path(case["code_file"]).parent
        for name, expected in case["hashes"].items():
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected


def valid_loop():
    steps = [{"step": 1, "tool_call": {"name": "apply_patch"},
              "tool_result": {"status": "success", "evidence": {}, "candidate_version": "v2"}}]
    for index, name in enumerate(("validate_packages", "validate_apis", "execute", "run_pytest"), 2):
        steps.append({"step": index, "tool_call": {"name": name},
                      "tool_result": {"status": "success", "evidence": {"passed": True},
                                      "candidate_version": "v2"}})
    return {"trajectory": steps, "candidate_version": "v2", "final_status": "PASS",
            "termination_reason": "finish"}


def test_rescue_counts_real_current_evidence_only():
    baseline = {"repair_attempted": True, "status": "FAIL"}
    assert rescue_details(baseline, valid_loop())["rescued_at_step"] == 5
    assert not rescue_details({"repair_attempted": False, "status": "FAIL"}, valid_loop())["rescued"]
    assert not rescue_details({"repair_attempted": True, "status": "ERROR"}, valid_loop())["rescued"]
    for field, value in (("status", "mock"), ("candidate_version", "old")):
        loop = valid_loop()
        loop["trajectory"][-1]["tool_result"][field] = value
        assert not rescue_details(baseline, loop)["rescued"]
    loop = valid_loop()
    loop["trajectory"] = []
    assert not rescue_details(baseline, loop)["rescued"]
    assert not rescue_details(baseline, None)["rescued"]
