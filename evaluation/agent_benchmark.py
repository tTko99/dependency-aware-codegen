"""Auditable live comparison and explicitly labelled historical replay.

python -m evaluation.agent_benchmark --mode replay
python -m evaluation.agent_benchmark --mode live
Replay never reports model rescue counts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from depguard.agent.loop import AgentLoop
from depguard.agent.safety import load_state
from depguard.cli import _derive_final_status
from depguard.config import load_config
from depguard.execution import SandboxedExecutor
from depguard.models.agent import OllamaAgentModel
from depguard.models.ollama import OllamaRepairModel
from depguard.pipeline import DependencyGuardPipeline
from depguard.schemas import to_jsonable


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_hashes(case):
    return {name: sha(Path(case[name]).read_bytes()) for name in ("code_file", "test_file")}


class RecordedRepair:
    model_name = "historical-output-replay-NOT-live-model"

    def __init__(self, code):
        self.code = code

    def repair(self, context):
        return self.code


def one_shot(case, model, timeout):
    started = time.monotonic()
    try:
        pipeline = DependencyGuardPipeline(repair_model=model, repair_method="ollama",
                                           executor=SandboxedExecutor(timeout_seconds=timeout))
        result = pipeline.run(requirement=case["requirement"],
                              code=Path(case["code_file"]).read_text(encoding="utf-8"),
                              test_code=Path(case["test_file"]).read_text(encoding="utf-8"))
        return {"status": _derive_final_status(result), "result": to_jsonable(result),
                "repair_attempted": result.repaired_code is not None,
                "termination_reason": "one_shot_complete",
                "elapsed_seconds": time.monotonic()-started}
    except Exception as exc:  # noqa: BLE001 - report per-case infrastructure failures
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}",
                "repair_attempted": False, "termination_reason": "backend_error",
                "elapsed_seconds": time.monotonic()-started}


def rescue_details(baseline, loop):
    """Use actual current run evidence, never model prose or historical cohort labels."""
    first_failed = baseline["repair_attempted"] and baseline["status"] == "FAIL"
    if not loop:
        return {"first_failed": first_failed, "rescued": False, "rescued_at_step": None}
    trajectory = loop["trajectory"]
    patches = [step["step"] for step in trajectory
               if step["tool_call"] and step["tool_call"]["name"] == "apply_patch"
               and step["tool_result"]["status"] == "success"]
    version = loop["candidate_version"]
    checks = {step["tool_call"]["name"]: step["step"] for step in trajectory
              if step["tool_call"] and step["tool_result"]["status"] == "success"
              and step["tool_result"]["evidence"].get("passed") is True
              and step["tool_result"]["candidate_version"] == version}
    required = {"validate_packages", "validate_apis", "execute", "run_pytest"}
    rescued = bool(first_failed and patches and required <= checks.keys()
                   and loop["final_status"] == "PASS" and loop["termination_reason"] == "finish")
    return {"first_failed": first_failed, "rescued": rescued,
            "rescued_at_step": max(checks.values()) if rescued else None,
            "successful_patch_steps": patches}


def run(mode, config_path, output_dir):
    config = load_config(config_path)
    model_options = config["repair"]["ollama"]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    environment = {"python": sys.version, "platform": platform.platform(),
                   "packages": {name: importlib.metadata.version(name)
                                for name in ("pytest", "numpy", "scipy", "pyyaml")}}
    metadata = {"mode": mode, "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment": environment, "config": config,
                "config_sha256": sha(Path(config_path).read_bytes())}
    if mode == "live":
        try:
            metadata["model_identity"] = OllamaRepairModel(**model_options).runtime_metadata()
        except Exception as exc:  # noqa: BLE001 - preserve backend outage evidence
            metadata["model_unavailable"] = f"{type(exc).__name__}: {exc}"
    else:
        metadata["scope"] = "Historical output replay with real execution; NOT live inference"
    sanity = json.loads(Path("data/engineering_sanity/manifest.json").read_text())
    sanity_config = load_config("configs/engineering_7b_ollama.yaml")
    metadata["sanity_config"] = sanity_config
    metadata["sanity_config_sha256"] = sha(Path("configs/engineering_7b_ollama.yaml").read_bytes())
    historical_hashes = json.loads(Path("data/engineering_sanity/source_hashes.json").read_text())
    rows = []
    # Always complete sanity first, before entering the failure cohort.
    for case in sanity["cases"]:
        before = file_hashes(case)
        record = json.loads(Path(
            f"results/engineering_sanity_7b_ollama/{case['id']}.json",
        ).read_text())
        model = (RecordedRepair(record["repaired_code"]) if mode == "replay"
                 else OllamaRepairModel(**sanity_config["repair"]["ollama"]))
        baseline = one_shot(case, model, sanity_config["execution"]["timeout_seconds"])
        normalized = {key: sha(Path(case[key]).read_bytes().replace(b"\r\n", b"\n"))
                      == historical_hashes["cases"][case["id"]][historical]
                      for key, historical in [("code_file", "code_sha256"),
                                              ("test_file", "test_sha256")]}
        row = {"id": case["id"], "cohort": "sanity", "mode": mode,
               "is_control": case["initial_problem_category"] == "correct_control",
               "before_hashes": before, "after_hashes": file_hashes(case),
               "unchanged": before == file_hashes(case), "historical_lf_match": normalized,
               "one_shot": baseline}
        rows.append(row)
        (destination / f"sanity_{case['id']}.json").write_text(json.dumps(row, indent=2))
    manifest_path = Path("data/agent_failures/manifest.json")
    manifest = json.loads(manifest_path.read_text())
    metadata["failure_manifest_sha256"] = sha(manifest_path.read_bytes())
    if sha(Path(config_path).read_bytes()) != manifest["comparison_config_sha256"]:
        raise ValueError("Comparison config changed; freeze a new manifest explicitly")
    for case in manifest["cases"]:
        before = file_hashes(case)
        for name, expected in case["hashes"].items():
            if sha((Path(case["code_file"]).parent / name).read_bytes()) != expected:
                raise ValueError(f"Frozen fixture hash mismatch: {case['id']}/{name}")
        model = (RecordedRepair(Path(case["historical_repair_file"]).read_text())
                 if mode == "replay" else OllamaRepairModel(**model_options))
        baseline = one_shot(case, model, config["execution"]["timeout_seconds"])
        loop = None
        if mode == "live":
            state = load_state(case["code_file"], case["test_file"],
                               execution_timeout_seconds=config["execution"]["timeout_seconds"])
            loop = to_jsonable(AgentLoop(OllamaAgentModel(**model_options),
                                         **config["agent"]).run(state, case["requirement"]))
        row = {"id": case["id"], "cohort": "historical_failures", "mode": mode,
               "before_hashes": before, "after_hashes": file_hashes(case),
               "unchanged": before == file_hashes(case), "one_shot": baseline, "loop": loop,
               **rescue_details(baseline, loop)}
        rows.append(row)
        (destination / f"failure_{case['id']}.json").write_text(json.dumps(row, indent=2))
    failures = [row for row in rows if row["cohort"] == "historical_failures"]
    complete = (mode == "live" and "model_unavailable" not in metadata
                and all(row["one_shot"]["status"] != "ERROR" for row in rows)
                and all(row["loop"]["termination_reason"] != "model_error" for row in failures))
    summary = {
        **metadata, "comparison_complete": complete,
        "sanity_repaired_pass": sum(row["cohort"] == "sanity" and not row["is_control"]
                                    and row["one_shot"]["status"] == "PASS" for row in rows),
        "sanity_controls_preserved": sum(row["cohort"] == "sanity" and row["is_control"]
                                         and row["one_shot"]["status"] == "NO_REPAIR_NEEDED"
                                         for row in rows),
        "all_inputs_unchanged": all(row["unchanged"] for row in rows),
        "rescued": sum(row["rescued"] for row in failures) if complete else None,
        "single_shot_failed": sum(row["first_failed"] for row in failures) if complete else None,
        "historical_failure_replay_count": sum(row["first_failed"] for row in failures)
        if mode == "replay" else None,
        "case_results": [{"id": row["id"], "cohort": row["cohort"],
                          "one_shot_status": row["one_shot"]["status"]} for row in rows],
    }
    (destination / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["replay", "live"], required=True)
    parser.add_argument("--config", default="configs/agent_evaluation.json")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    run(args.mode, args.config, args.output_dir or f"results/agent_evaluation/{args.mode}")


if __name__ == "__main__":
    main()
