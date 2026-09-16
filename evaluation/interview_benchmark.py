"""M7 paired evaluation. Reuses M4 manifest/hash helpers and M6 tool/persistence boundaries."""
from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from depguard.agent.context import compact_observation
from depguard.agent.contracts import ToolCall
from depguard.agent.deadline import bounded
from depguard.agent.loop import AgentLoop, decide_worker
from depguard.agent.patching import apply_patch, normalized_diff
from depguard.agent.persistence import _atomic_write
from depguard.agent.regression import verification
from depguard.agent.runner import run_agent
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry, dispatch_worker
from depguard.config import load_config
from depguard.models.agent import OllamaAgentModel
from depguard.models.cloud import CloudToolCallingModel
from depguard.repair.prompts import strip_code_fence
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import RecordedRepair, file_hashes, one_shot, sha


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(value, secrets=()):
    """Do not serialize credentials, auth headers, home paths or environment dumps."""
    if isinstance(value, dict):
        return {k: clean(v, secrets) for k, v in value.items()
                if k.lower() not in {"api_key", "authorization", "headers", "environment_variables"}}
    if isinstance(value, (list, tuple)):
        return [clean(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value.replace(str(Path.home()), "<home>").replace(str(Path.cwd()), "<project>")
    return value


def save(path, payload, secrets=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, (json.dumps(clean(payload, secrets), indent=2)+"\n").encode())


def verify_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        folder = Path(case["code_file"]).parent
        for name, expected in case["hashes"].items():
            if sha((folder / name).read_bytes()) != expected:
                raise ValueError(f"MANIFEST_HASH_MISMATCH: {case['id']}/{name}")
    for name, expected in manifest["configs"].items():
        if sha(Path(name).read_bytes()) != expected:
            raise ValueError("FROZEN_CONFIG_CHANGED: create a new explicit freeze, never alter an existing run")
    return manifest


def make_model(config):
    cls = OllamaAgentModel if config["provider"] == "ollama" else CloudToolCallingModel
    return cls(**config["model"])


def freeze_config(manifest_path, config_path, output):
    """Pin a NEW configuration without mutating the original frozen dataset or config."""
    manifest = verify_manifest(manifest_path)
    config = load_config(config_path)
    make_model(config)  # Validate endpoint/options without network or credential reads.
    if config["model"]["model_name"].startswith("REPLACE_"):
        raise ValueError("Select an explicit model first")
    if output.exists():
        raise FileExistsError("New freeze must not replace any previous manifest")
    manifest["parent_manifest_sha256"] = sha(manifest_path.read_bytes())
    manifest["configs"] = {str(config_path): sha(config_path.read_bytes())}
    save(output, manifest)
    return manifest


def host_checks(state, deadline):
    # Always rerun real checks for the final independent audit; no model-owned cache.
    checked = copy.deepcopy(state)
    checked.call_counts.clear()
    checked.cache.clear()
    checked.passed_checks.clear()
    checked.check_state_versions.clear()
    checked.allow_test_rerun = True
    registry = default_registry()
    evidence = {}
    for name in sorted(state.required_checks):
        result, checked = bounded(dispatch_worker, (registry, checked, ToolCall(name), deadline), deadline)
        evidence[name] = to_jsonable(result)
    result = verification(checked)
    result["checks"] = evidence
    state.passed_checks = checked.passed_checks
    state.check_state_versions = checked.check_state_versions
    state.check_results = checked.check_results
    state.check_result_contexts = checked.check_result_contexts
    return result


def token_totals(records):
    if not records:
        return {"input": 0, "output": 0}
    usages = [r.get("usage", {}) for r in records if isinstance(r, dict)]
    if len(usages) != len(records) or any(not u for u in usages):
        return None
    return {"input": sum(u.get("prompt_tokens", u.get("prompt_eval_count", 0)) for u in usages),
            "output": sum(u.get("completion_tokens", u.get("eval_count", 0)) for u in usages)}


def evaluate_case(case, condition, config, model, *, mode="live", trigger_gate=False):
    before = file_hashes(case)
    started = time.monotonic()
    state = load_state(case["code_file"], case["test_file"],
                       project_root=Path(case["code_file"]).parent,
                       execution_timeout_seconds=config["execution_timeout_seconds"],
                       validation_config={"required_checks": case["required_checks"]})
    deadline = started + config["agent"]["timeout_seconds"]
    trajectory, raw_responses = [], []
    row = {"case_id": case["id"], "cohort": case["cohort"], "is_control": case["is_control"],
           "mode": mode, "condition": condition, "attempted": True, "started": now(),
           "required_checks": case["required_checks"], "before_hashes": before,
           "capability_probe": {}, "repair_attempted": False, "model_calls": 0,
           "status": "ERROR", "termination_reason": "evaluation_error", "trajectory": [],
           "final_verification": {}, "apply": False, "rollback": {"attempted": False}}
    try:
        initial = None
        if config.get("shared_initial_evidence") and not (trigger_gate and condition == "loop"):
            initial = host_checks(state, deadline)
            row["initial_verification"] = initial
            state.initial_evidence = {**initial, "checks": {
                name: compact_observation(result, config["agent"]["output_limit"])
                for name, result in initial["checks"].items()}}
        if condition == "one-shot":
            initial = initial or host_checks(state, deadline)
            row["initial_verification"] = initial
            if initial["host_status"] == "PASS":
                row.update(status="NO_REPAIR_NEEDED", termination_reason="no_repair_needed",
                           final_verification=initial)
            else:
                messages = [{"role": "system", "content": "Repair the Python program. Return only the complete corrected program; no tools or explanation. Preserve public APIs and all functionality."},
                    {"role": "user", "content": json.dumps({"requirement": case["requirement"],
                        "source": state.candidate_code, "tests": state.test_code,
                        "initial_evidence": state.initial_evidence or initial})}]
                row["model_calls"] = 1
                decision, model = bounded(decide_worker, (model, messages, [],
                    max(.001, deadline-time.monotonic())), deadline)
                row["repair_attempted"] = True
                raw = to_jsonable(decision.raw_response)
                raw_responses.append(raw or {})
                row["model_response"] = raw
                if decision.kind != "text":
                    row.update(status="ERROR", termination_reason=decision.error_code or "one_shot_nontext")
                else:
                    content = strip_code_fence((raw or {}).get("content", ""))
                    if state.original_code.endswith("\n"):
                        content += "\n"
                    patch = normalized_diff(state.candidate_code, content, "input.py")
                    applied = apply_patch(state, {"patch": patch}, deadline)
                    row["patch_submission"] = to_jsonable(applied)
                    row["final_verification"] = host_checks(state, time.monotonic()+30)
                    row.update(status=row["final_verification"]["host_status"],
                               termination_reason="one_shot_complete")
        else:
            loop = AgentLoop(model, **config["agent"])
            run = to_jsonable(run_agent(loop, state, case["requirement"]) if trigger_gate
                              else loop.run(state, case["requirement"]))
            row["agent_invoked"] = run["agent_invoked"]
            row["rejected_finish_count"] = run["rejected_finish_count"]
            if run["initial_verification"]:
                row["initial_verification"] = run["initial_verification"]
            trajectory = run["trajectory"]
            for index, step in enumerate(trajectory):
                step["observed_steps"] = [s["step"] for s in trajectory[max(0,index-config["agent"]["recent_steps"]):index]]
            raw_responses = [s.get("raw_response") or {} for s in trajectory]
            probe = run["capability_probe"]
            raw_responses += probe.get("transcript", [])
            row.update(status=run["final_status"], termination_reason=run["termination_reason"],
                       capability_probe=probe, model_calls=len(trajectory)+len(probe.get("transcript", [])),
                       loop_result=run, repair_attempted=bool(state.applied_patches))
            # This independent audit has the SAME fixed allowance for both arms. A loop
            # still needs a verified finish; passing unchanged input never upgrades it.
            row["final_verification"] = (run["initial_verification"] if row["status"] == "NO_REPAIR_NEEDED"
                                         else host_checks(state, time.monotonic()+30))
            if row["status"] in {"PASS", "NO_REPAIR_NEEDED"} and row["final_verification"]["host_status"] != "PASS":
                row["status"] = "FAIL"
        if not row["final_verification"]:
            row["final_verification"] = host_checks(state, time.monotonic()+30)
    except Exception as exc:  # noqa: BLE001 - complete each artifact, exclude infrastructure failures
        row.update(status="ERROR", termination_reason=type(exc).__name__, failure_classification="infrastructure")
    row.update(ended=now(), latency=time.monotonic()-started, trajectory=trajectory,
               after_hashes=file_hashes(case), unchanged=before == file_hashes(case),
               candidate_changed=state.candidate_code != state.original_code,
               candidate_code=state.candidate_code, candidate_version=state.version,
               candidate_versions=[s.get("candidate_version") for s in trajectory],
               patches=state.applied_patches, patch_count=len(state.applied_patches),
               verification_count=sum((s.get("tool_call") or {}).get("name") in case["required_checks"] for s in trajectory),
               tokens=token_totals(raw_responses))
    row.setdefault("failure_classification", row["termination_reason"] if row["status"] not in {"PASS", "NO_REPAIR_NEEDED"} else None)
    return row


def start_run(output, manifest_path, config_path):
    manifest = verify_manifest(manifest_path)
    config = load_config(config_path)
    if config["provider"] not in {"ollama", "cloud"}:
        raise ValueError("Real comparison only supports actual providers")
    identity = {"manifest_sha256": sha(manifest_path.read_bytes()), "config_sha256": sha(config_path.read_bytes()),
                "environment": {"python": sys.version, "platform": platform.platform()},
                "resolved_config": config, "provider": config["provider"], "model": config["model"]["model_name"]}
    if str(config_path) not in manifest["configs"]:
        raise ValueError("Configuration was not frozen with this manifest")
    if config["provider"] == "ollama":
        try:
            model = make_model(config)
            metadata = model.runtime_metadata()
            identity["model_digest"] = metadata["installed_model"]["digest"]
            identity["ollama_version"] = metadata["ollama_version"]
        except Exception:  # noqa: BLE001 - classify unavailable provider without exposing errors
            identity["model_digest"] = "UNAVAILABLE"
    else:
        identity["model_digest"] = "provider model label; immutable version not independently verified"
    run_path = output / "run_manifest.json"
    comparison = sha(json.dumps(identity, sort_keys=True).encode())
    if run_path.exists():
        run = json.loads(run_path.read_text())
        if run["comparison_identity"] != comparison:
            raise ValueError("Run identity changed; resume requires same manifest/config/model/environment")
    else:
        if output.exists() and any(output.iterdir()):
            raise ValueError("Use a new empty output directory")
        run = {**identity, "run_id": output.name + "-" + comparison[:12], "started": now(),
               "comparison_identity": comparison, "artifact_hashes": {}}
        save(run_path, run)
    return manifest, config, run


def run_comparison(output, manifest_path, config_path, condition, *, after_case=None, trigger_gate=False):
    manifest, config, run = start_run(output, manifest_path, config_path)
    secret = os.environ.get(config["model"].get("api_key_env", ""), "")
    for case in manifest["cases"]:
        if case["cohort"] not in {"hard", "control"}:
            continue
        verify_manifest(manifest_path)
        name = f"{condition}_{case['id']}.json"
        path = output / name
        if name in run["artifact_hashes"]:
            if sha(path.read_bytes()) != run["artifact_hashes"][name]:
                raise ValueError("Completed artifact changed")
            continue
        if config["provider"] == "cloud" and not secret:
            row = {"case_id": case["id"], "cohort": case["cohort"], "is_control": case["is_control"],
                   "condition": condition, "mode": "live", "attempted": False,
                   "status": "NOT_RUN_NO_CREDENTIALS", "started": now(), "ended": now()}
        elif config["provider"] == "cloud" and config["model"]["model_name"].startswith("REPLACE_"):
            raise ValueError("Pin cloud model in a newly frozen configuration before live calls")
        else:
            row = evaluate_case(case, condition, config, make_model(config), trigger_gate=trigger_gate)
        row.update(run_id=run["run_id"], comparison_identity=run["comparison_identity"],
                   provider=run["provider"], model=run["model"], resolved_config=config)
        # Complete per-case artifact precedes the resumable index; raw result references
        # use the existing trajectory/tool_result structure rather than duplicate logs.
        row["raw_results_ref"] = name + "#/trajectory"
        save(path, row, (secret,))
        run["artifact_hashes"][name] = sha(path.read_bytes())
        save(output / "run_manifest.json", run)
        print(f"{condition} {case['id']}: {row['status']}", flush=True)
        if after_case:
            after_case(row)
    return run


def sanity(output, live=False):
    """Same M4 pipeline/artifacts, separate regression label; never a rescue denominator."""
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use new sanity output directory")
    manifest = json.loads(Path("data/engineering_sanity/manifest.json").read_text())
    config = load_config(manifest["config"])
    rows = []
    model = OllamaAgentModel(**config["repair"]["ollama"])
    runtime = model.runtime_metadata() if live else {"mode": "historical repair replay; no inference"}
    for case in manifest["cases"]:
        before = file_hashes(case)
        recorded = json.loads(Path(f"results/engineering_sanity_7b_ollama/{case['id']}.json").read_text())
        baseline = one_shot(case, model if live else RecordedRepair(recorded["repaired_code"]),
                            config["execution"]["timeout_seconds"])
        row = {"id": case["id"], "is_control": case["initial_problem_category"] == "correct_control",
               "one_shot": baseline, "unchanged": before == file_hashes(case),
               "before_hashes": before, "after_hashes": file_hashes(case)}
        save(output / (case["id"]+".json"), row)
        rows.append(row)
        print(f"sanity {case['id']}: {baseline['status']}", flush=True)
    summary = {"mode": "live" if live else "historical_output_replay", "runtime": runtime,
               "config": config, "environment": {"python": sys.version, "platform": platform.platform()},
               "repairs_passed": sum(not r["is_control"] and r["one_shot"]["status"] == "PASS" for r in rows),
               "controls_preserved": sum(r["is_control"] and r["one_shot"]["status"] == "NO_REPAIR_NEEDED" for r in rows),
               "all_inputs_unchanged": all(r["unchanged"] for r in rows)}
    save(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["sanity", "one-shot", "loop", "infrastructure", "report", "freeze-config"])
    parser.add_argument("--manifest", default="data/interview_eval/manifest.json")
    parser.add_argument("--config", default="configs/m7_ollama.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--live", action="store_true", help="Live model only for sanity; comparison commands are live")
    parser.add_argument("--infrastructure-dir")
    parser.add_argument("--sanity-dir")
    args = parser.parse_args()
    output = Path(args.output_dir)
    if args.command == "freeze-config":
        freeze_config(Path(args.manifest), Path(args.config), output / "manifest.json")
    elif args.command == "sanity":
        sanity(output, args.live)
    elif args.command == "report":
        from evaluation.interview_report import report
        report(output, Path(args.infrastructure_dir) if args.infrastructure_dir else None,
               Path(args.sanity_dir) if args.sanity_dir else None)
    elif args.command == "infrastructure":
        from evaluation.interview_infrastructure import run
        run(output, Path(args.manifest))
    else:
        run_comparison(output, Path(args.manifest), Path(args.config), args.command)


if __name__ == "__main__":
    main()
