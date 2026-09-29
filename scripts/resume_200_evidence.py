"""Audit an externally interrupted attempt without retrying or changing frozen code."""
import json
from pathlib import Path

from evaluation.agent_benchmark import file_hashes, sha
from evaluation.interview_benchmark import now, save, verify_manifest
from scripts.expansion200_run import OUTPUT
from scripts.expansion200_run import verify as verify_freeze


def main():
    frozen = verify_freeze()
    audit = OUTPUT / "recovery"
    audit.mkdir(exist_ok=True)
    index_path = OUTPUT / "run_manifest.json"
    original = index_path.read_bytes()
    index = json.loads(original)
    cases = {c["id"]: c for c in verify_manifest(
        Path(frozen["manifest"]))["cases"]}
    for name, attempt in index["attempts"].items():
        if attempt["status"] != "running" or name in index["artifact_hashes"]:
            continue
        destination = index_path.parent / "cases" / name
        if destination.exists():
            raise ValueError("Orphan completed artifact requires separate review; do not overwrite")
        if name != "loop_hep_154.json":
            raise ValueError("Unexpected interrupted attempt; inspect before recovering")
        before = audit / "run_manifest_before_recovery.json"
        if before.exists() and before.read_bytes() != original:
            raise ValueError("Prior recovery audit exists")
        before.write_bytes(original)
        case = cases["hep_154"]
        source = Path(case["code_file"]).read_text(encoding="utf-8")
        hashes = file_hashes(case)
        row = {"case_id": case["id"], "condition": "loop", "cohort": "hard",
            "is_control": False, "mode": "live", "attempted": True,
            "status": "ERROR", "termination_reason": "evaluation_interrupted_unknown_result",
            "started": attempt["started"], "ended": None, "audited_at": now(),
            "agent_invoked": None, "capability_probe": {}, "trajectory": [],
            "repair_attempted": None, "patch_count": 0, "patches": [],
            "candidate_code": source, "candidate_version": "0:" + sha(source.encode()),
            "candidate_changed": False, "required_checks": case["required_checks"],
            "final_verification": {}, "initial_verification": {},
            "before_hashes": hashes, "after_hashes": hashes, "unchanged": True,
            "apply": False, "model_calls": 0, "latency": 0, "tokens": None,
            "cost_measurement": "UNAVAILABLE; zero placeholders are NOT actual measured costs",
            "measurement_status": "interrupted_unknown",
            "candidate_state": "last durable input only; intermediate state unavailable",
            "comparison_identity": frozen["freeze_id"], "run_id": "expansion200_v1",
            "evaluation_cohort": case["provenance"]["kind"], "family": case["family"],
            "category": case["category"], "provenance": case["provenance"],
            "provider": "ollama", "model": frozen["model_identity"]["model"],
            "resolved_config": frozen["resolved_config"],
            "failure_classification": "external_interruption_not_model_failure"}
        save(destination, row)
        index["artifact_hashes"][name] = sha(destination.read_bytes())
        attempt.update(status="audited_interruption", audited_at=now(), retried=False)
        save(index_path, index)
        save(audit / "interruption.json", {"artifact": name, "retried": False,
            "prior_manifest_sha256": sha(original), "detected_at": now(),
            "evidence": "Worker exited after evaluate_case returned: post-run runtime_metadata failed because Ollama refused connection. No final artifact was saved; outcome and trajectory cannot be reconstructed.",
            "treatment": "Retain in planned repair denominator as not demonstrated PASS; "
                         "exclude unknown cost from measured cost averages and protocol denominator.",
            "recovery_script_sha256": sha(Path(__file__).read_bytes())})
        print("Interrupted attempt preserved as unknown; no new inference for this case", flush=True)
    verify_freeze()
    print("Audit complete; resume only unstarted attempts after service identity verification", flush=True)


if __name__ == "__main__":
    main()
