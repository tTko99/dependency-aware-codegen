"""Audit an externally interrupted attempt without retrying or changing frozen code."""
import json
from pathlib import Path

from evaluation.agent_benchmark import file_hashes, sha
from evaluation.external_validation import OUTPUT, check_runtime, verify_freeze
from evaluation.interview_benchmark import make_model, now, save, verify_manifest


def main():
    frozen = verify_freeze()
    audit = OUTPUT / "recovery"
    audit.mkdir(exist_ok=True)
    index_path = OUTPUT / "external/run_manifest.json"
    original = index_path.read_bytes()
    index = json.loads(original)
    cases = {c["id"]: c for c in verify_manifest(
        Path(frozen["manifests"]["external"]))["cases"]}
    for name, attempt in index["attempts"].items():
        if attempt["status"] != "running" or name in index["artifact_hashes"]:
            continue
        destination = index_path.parent / name
        if destination.exists():
            raise ValueError("Orphan completed artifact requires separate review; do not overwrite")
        if name != "loop_qb_levenshtein.json":
            raise ValueError("Unexpected interrupted attempt; inspect before recovering")
        before = audit / "run_manifest_before_recovery.json"
        if before.exists() and before.read_bytes() != original:
            raise ValueError("Prior recovery audit exists")
        before.write_bytes(original)
        case = cases["qb_levenshtein"]
        source = Path(case["code_file"]).read_text()
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
            "comparison_identity": frozen["freeze_id"], "run_id": index["run_id"],
            "evaluation_cohort": "external", "family": case["family"],
            "provider": "ollama", "model": frozen["model_identity"]["model"],
            "resolved_config": frozen["resolved_config"],
            "failure_classification": "external_interruption_not_model_failure"}
        save(destination, row)
        index["artifact_hashes"][name] = sha(destination.read_bytes())
        attempt.update(status="audited_interruption", audited_at=now(), retried=False)
        save(index_path, index)
        save(audit / "interruption.json", {"artifact": name, "retried": False,
            "prior_manifest_sha256": sha(original), "detected_at": now(),
            "evidence": "No Python worker remained; started marker exists, no final artifact.",
            "treatment": "Retain in planned repair denominator as not demonstrated PASS; "
                         "exclude unknown cost from measured cost averages and protocol denominator.",
            "recovery_script_sha256": sha(Path(__file__).read_bytes())})
        print("Interrupted attempt preserved as unknown; no new inference for this case", flush=True)
    model = make_model(frozen["resolved_config"])
    runtime = check_runtime(model, frozen)
    if not runtime.get("runtime") or runtime["runtime"]["context_length"] != 16384:
        response = model._post_json("/api/generate", {
            "model": model.model_name, "prompt": "", "stream": False,
            "keep_alive": "10m", "options": {"num_ctx": 16384, "temperature": 0}})
        save(audit / "warmup.json", {"purpose": "Load only; empty prompt, no benchmark task",
            "model": response.get("model"), "done_reason": response.get("done_reason"),
            "runtime": check_runtime(model, frozen, loaded=True)})
    verify_freeze()
    print("Ready to resume unstarted tasks with the unchanged frozen evaluator", flush=True)


if __name__ == "__main__":
    main()
