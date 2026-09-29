"""Freeze, resume and audit an independent local-model comparison without tuning the Agent."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import evaluate_case, make_model, now, save, verify_manifest
from evaluation.prepare_external import CONFIG, DATA, immutable

OUTPUT = Path("results/external_eval_v1")
OLD_MANIFEST = Path("results/qwen3_validation/frozen/manifest.json")


def fingerprint(paths):
    return {p.as_posix(): sha(p.read_bytes()) for p in sorted(set(paths)) if p.is_file()}


def implementation_files():
    return [*Path("src").rglob("*.py"), *Path("evaluation").glob("*.py"),
            *Path("tests").glob("*.py"), Path("pyproject.toml")]


def historical_files():
    roots = ["data/interview_eval", "data/engineering_sanity", "data/agent_failures",
             "results/m72", "results/qwen3_validation"]
    return [p for root in roots for p in Path(root).rglob("*") if p.is_file()]


def environment():
    return {"python": sys.version, "platform": platform.platform(),
            "packages": {k: importlib.metadata.version(k) for k in ("pytest", "pyyaml")}}


def identity(runtime):
    installed = runtime.get("installed_model") or {}
    if not installed.get("digest") or not runtime.get("ollama_version"):
        raise ValueError("Model digest and Ollama version are required")
    return {"model": installed["name"], "digest": installed["digest"],
            "ollama_version": runtime["ollama_version"]}


def verify_hashes(expected):
    for name, digest in expected.items():
        path = Path(name)
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError(f"Frozen evidence changed: {name}")


def freeze():
    target = OUTPUT / "freeze.json"
    if target.exists():
        raise FileExistsError("Freeze already exists; resume it instead")
    manifest = verify_manifest(DATA / "draft_manifest.json")
    preflight = json.loads((DATA / "preflight_summary.json").read_text())
    if preflight["invalid"] or preflight["valid"] != len(manifest["cases"]):
        raise ValueError("Every included case needs passing source/reference preflight")
    # Verify each record, not merely a caller-supplied aggregate count.
    for case in manifest["cases"]:
        record = json.loads((DATA / "preflight" / (case["id"] + ".json")).read_text())
        if record["case_id"] != case["id"] or not record["valid"]:
            raise ValueError("Invalid preflight record")
    config = json.loads(CONFIG.read_text())
    if config["provider"] != "ollama" or config["model"]["base_url"] not in {
        "http://localhost:11434", "http://127.0.0.1:11434"
    }:
        raise ValueError("This comparison only permits local Ollama")
    runtime = make_model(config).runtime_metadata()
    model_identity = identity(runtime)
    old = json.loads(Path("results/m72/comparison/run_manifest.json").read_text())
    if model_identity["digest"] != old["model_digest"]:
        raise ValueError("Expected the existing 30B digest")
    immutable(DATA / "manifest.json", (DATA / "draft_manifest.json").read_bytes())
    protected = fingerprint([*DATA.rglob("*"), *historical_files(), CONFIG, OLD_MANIFEST])
    frozen = {"schema_version": 1, "frozen_at": now(), "model_identity": model_identity,
        "environment": environment(), "runtime_before": runtime, "resolved_config": config,
        "implementation_sha256": fingerprint(implementation_files()), "protected_sha256": protected,
        "manifests": {"external": (DATA / "manifest.json").as_posix(),
                      "regression": OLD_MANIFEST.as_posix()},
        "policy": {"one_attempt_per_condition": True, "no_outcome_based_tuning": True,
            "order": "external then regression; alternate paired condition order by case index",
            "repair_denominator": "all planned defective cases, including errors and rejections",
            "controls_separate": True, "formal_checks": "same existing host checks for both arms",
            "strict_rescue": "unchanged evaluation/interview_metrics.py definition",
            "budget": "2048 output tokens/call, 300s task + 30s final audit; loop up to 24 steps",
            "not_equal_total_token_budget": True, "visible_tests": True,
            "human_acceptance": "not measured; test PASS is not human acceptance",
            "population_claim": "none; public algorithm benchmark, unknown training contamination"}}
    frozen["freeze_id"] = sha(json.dumps(frozen, sort_keys=True).encode())
    save(target, frozen)
    save(OUTPUT / "resolved_config.json", config)
    print(f"Frozen {len(manifest['cases'])} external and 15 regression cases; no inference yet")


def verify_freeze():
    frozen = json.loads((OUTPUT / "freeze.json").read_text())
    freeze_id = frozen.pop("freeze_id")
    if sha(json.dumps(frozen, sort_keys=True).encode()) != freeze_id:
        raise ValueError("Freeze metadata changed")
    frozen["freeze_id"] = freeze_id
    verify_hashes(frozen["protected_sha256"])
    if fingerprint(implementation_files()) != frozen["implementation_sha256"]:
        raise ValueError("Implementation changed after freeze")
    if environment() != frozen["environment"]:
        raise ValueError("Python evaluation environment changed")
    return frozen


def check_runtime(model, frozen, *, loaded=False):
    runtime = model.runtime_metadata()
    if identity(runtime) != frozen["model_identity"]:
        raise ValueError("Model identity changed")
    resident = runtime.get("runtime")
    if loaded and (not resident or resident["context_length"] != 16384):
        raise ValueError("Loaded context must be 16384")
    # Do not share GPU with another Ollama model during measurements.
    running = model._get_json("/api/ps").get("models", [])
    if any(m.get("digest") != frozen["model_identity"]["digest"] for m in running):
        raise ValueError("Another model is resident; stop it before evaluation")
    return runtime


def run():
    frozen = verify_freeze()
    config = frozen["resolved_config"]
    model = make_model(config)
    runtime = check_runtime(model, frozen)
    probe_path = OUTPUT / "capability_probe.json"
    if not probe_path.exists():
        result = to_jsonable(run_probe(model, default_registry().specs,
                            timeout_seconds=config["agent"]["probe_timeout"], use_cache=False))
        save(probe_path, {"result": result, "before": runtime,
                          "after": model.runtime_metadata(), "freeze_id": frozen["freeze_id"]})
    probe = json.loads(probe_path.read_text())
    if probe["freeze_id"] != frozen["freeze_id"] or probe["result"]["status"] != "passed":
        raise ValueError("Full probe failed; no formal cases run")
    check_runtime(model, frozen, loaded=True)
    print("Full native probe PASS; model identity and context verified", flush=True)
    for cohort, manifest_path in frozen["manifests"].items():
        cases = verify_manifest(Path(manifest_path))["cases"]
        cases = [c for c in cases if c["cohort"] in {"hard", "control"}]
        folder = OUTPUT / cohort
        index_path = folder / "run_manifest.json"
        if index_path.exists():
            index = json.loads(index_path.read_text())
            if index["freeze_id"] != frozen["freeze_id"]:
                raise ValueError("Resume freeze mismatch")
        else:
            index = {"freeze_id": frozen["freeze_id"], "cohort": cohort,
                "planned_cases": [c["id"] for c in cases], "artifact_hashes": {},
                "attempts": {}, "comparison_identity": frozen["freeze_id"],
                "run_id": "external-v1-" + cohort, "started": now()}
            save(index_path, index)
        for position, case in enumerate(cases):
            conditions = ["one-shot", "loop"] if position % 2 == 0 else ["loop", "one-shot"]
            for condition in conditions:
                verify_freeze()
                name = f"{condition}_{case['id']}.json"
                destination = folder / name
                if name in index["artifact_hashes"]:
                    if sha(destination.read_bytes()) != index["artifact_hashes"][name]:
                        raise ValueError("Completed artifact changed")
                    continue
                if name in index["attempts"] or destination.exists():
                    raise ValueError(f"Uncertain interrupted attempt {name}; retain and audit, no silent rerun")
                before = check_runtime(model, frozen)
                index["attempts"][name] = {"started": now(), "status": "running"}
                save(index_path, index)
                row = evaluate_case(case, condition, config, make_model(config), trigger_gate=True)
                row.update(comparison_identity=frozen["freeze_id"], run_id=index["run_id"],
                    evaluation_cohort=cohort, family=case.get("family", case["id"]),
                    provider="ollama", model=config["model"]["model_name"],
                    resolved_config=config, runtime_before=before,
                    runtime_after=check_runtime(model, frozen),
                    raw_results_ref=name + "#/trajectory")
                save(destination, row)
                index["artifact_hashes"][name] = sha(destination.read_bytes())
                index["attempts"][name].update(status="completed", ended=now())
                save(index_path, index)
                print(f"{cohort} {position+1}/{len(cases)} {condition} {case['id']}: "
                      f"{row['status']} ({row['latency']:.1f}s)", flush=True)
    verify_freeze()
    save(OUTPUT / "integrity_final.json", {"verified_at": now(), "all_frozen_files_unchanged": True,
        "runtime_after": check_runtime(model, frozen), "freeze_id": frozen["freeze_id"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["freeze", "run", "verify"])
    args = parser.parse_args()
    if args.stage == "freeze":
        freeze()
    elif args.stage == "run":
        run()
    else:
        verify_freeze()
        print("Frozen implementation, inputs and historical artifacts unchanged")
