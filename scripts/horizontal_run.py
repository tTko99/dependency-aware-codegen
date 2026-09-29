"""Frozen horizontal comparison. Existing Agent and evaluator remain byte-identical."""

import argparse
import json
from collections import Counter
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.external_validation import (
    check_runtime,
    environment,
    fingerprint,
    identity,
    implementation_files,
    verify_hashes,
)
from evaluation.external_validation import (
    verify_freeze as verify_previous,
)
from evaluation.interview_benchmark import evaluate_case, make_model, now, save, verify_manifest
from scripts.horizontal_prepare import DATA
from scripts.horizontal_sources import immutable

OUTPUT = Path("results/horizontal_eval_v1")
CONFIG = Path("configs/m7_qwen3_30b.json")


def implementation():
    return fingerprint([*implementation_files(), *Path("scripts").glob("horizontal*.py")])


def verify():
    frozen = json.loads((OUTPUT / "freeze.json").read_text(encoding="utf-8"))
    payload = dict(frozen)
    freeze_id = payload.pop("freeze_id")
    if sha(json.dumps(payload, sort_keys=True).encode()) != freeze_id:
        raise ValueError("Freeze metadata changed")
    verify_previous()
    verify_hashes(frozen["protected_sha256"])
    if (
        implementation() != frozen["implementation_sha256"]
        or environment() != frozen["environment"]
    ):
        raise ValueError("Implementation or environment changed")
    return frozen


def freeze():
    verify_previous()
    if (OUTPUT / "freeze.json").exists():
        raise ValueError("Already frozen")
    manifest = verify_manifest(DATA / "draft_manifest.json")
    for case in manifest["cases"]:
        row = json.loads((DATA / "preflight" / f"{case['id']}.json").read_text(encoding="utf-8"))
        if not row["valid"] or row["input_hashes"] != case["hashes"]:
            raise ValueError("Every selected case must pass current-input preflight")
    sources = [c["hashes"]["input.py"] for c in manifest["cases"] if not c["is_control"]]
    if len(set(sources)) != len(sources):
        raise ValueError("Duplicate defective input")
    previous = json.loads(Path("data/external_eval_v1/manifest.json").read_text())
    if set(sources) & {c["hashes"]["input.py"] for c in previous["cases"]}:
        raise ValueError("Duplicate historical input")
    config = json.loads(CONFIG.read_text())
    runtime = make_model(config).runtime_metadata()
    previous_frozen = verify_previous()
    if identity(runtime) != previous_frozen["model_identity"]:
        raise ValueError("Runtime identity changed; disclose and resolve before freezing")
    immutable(DATA / "manifest.json", (DATA / "draft_manifest.json").read_bytes())
    historical = [
        p
        for root in ("data/external_eval_v1", "results/external_eval_v1")
        for p in Path(root).rglob("*")
        if p.is_file()
    ]
    frozen = {
        "frozen_at": now(),
        "model_identity": identity(runtime),
        "environment": environment(),
        "resolved_config": config,
        "runtime_before": runtime,
        "implementation_sha256": implementation(),
        "protected_sha256": fingerprint(
            [*DATA.rglob("*"), *historical, CONFIG, Path("docs/HORIZONTAL_EVALUATION_PLAN.md")]
        ),
        "manifest": (DATA / "manifest.json").as_posix(),
        "policy": {
            "one_attempt_each": True,
            "paired_order": "alternate by manifest position",
            "agent_unchanged": True,
            "metrics_unchanged": True,
            "old_results_preserved": True,
            "source_groups_separate": True,
            "no_outcome_tuning": True,
            "all_formal_tests_visible": True,
            "human_acceptance": "not measured",
            "no_production_success_rate_claim": True,
            "controls_not_defect_denominator": True,
        },
        "source_counts": manifest["source_groups"],
        "category_counts": manifest["categories"],
    }
    frozen["freeze_id"] = sha(json.dumps(frozen, sort_keys=True).encode())
    save(OUTPUT / "freeze.json", frozen)
    save(OUTPUT / "resolved_config.json", config)
    print("Frozen " + str(len(manifest["cases"])) + " cases before inference", flush=True)


def run():
    frozen = verify()
    config = frozen["resolved_config"]
    model = make_model(config)
    runtime = check_runtime(model, frozen)
    if not runtime.get("runtime") or runtime["runtime"]["context_length"] != 16384:
        response = model._post_json(
            "/api/generate",
            {
                "model": model.model_name,
                "prompt": "",
                "stream": False,
                "keep_alive": "10m",
                "options": {"num_ctx": 16384, "temperature": 0},
            },
        )
        save(
            OUTPUT / "warmup.json",
            {
                "model": response.get("model"),
                "purpose": "empty prompt; no task inference",
                "runtime": check_runtime(model, frozen, loaded=True),
            },
        )
    probe_path = OUTPUT / "capability_probe.json"
    if not probe_path.exists():
        probe = to_jsonable(
            run_probe(
                model,
                default_registry().specs,
                timeout_seconds=config["agent"]["probe_timeout"],
                use_cache=False,
            )
        )
        save(
            probe_path,
            {
                "freeze_id": frozen["freeze_id"],
                "result": probe,
                "runtime": check_runtime(model, frozen, loaded=True),
            },
        )
    probe = json.loads(probe_path.read_text())
    if probe["freeze_id"] != frozen["freeze_id"] or probe["result"]["status"] != "passed":
        raise ValueError("Full native probe failed; formal evaluation blocked")
    cases = verify_manifest(DATA / "manifest.json")["cases"]
    index_path = OUTPUT / "run_manifest.json"
    index = (
        json.loads(index_path.read_text())
        if index_path.exists()
        else {
            "freeze_id": frozen["freeze_id"],
            "started": now(),
            "planned_cases": [c["id"] for c in cases],
            "attempts": {},
            "artifact_hashes": {},
        }
    )
    if index["freeze_id"] != frozen["freeze_id"]:
        raise ValueError("Run identity mismatch")
    for position, case in enumerate(cases):
        for condition in ["one-shot", "loop"] if position % 2 == 0 else ["loop", "one-shot"]:
            verify()
            name = f"{condition}_{case['id']}.json"
            destination = OUTPUT / "cases" / name
            if name in index["artifact_hashes"]:
                if sha(destination.read_bytes()) != index["artifact_hashes"][name]:
                    raise ValueError("Completed artifact changed")
                continue
            if name in index["attempts"] or destination.exists():
                raise ValueError(
                    "Interrupted attempt requires explicit audit, never silent rerun: " + name
                )
            before = check_runtime(model, frozen, loaded=True)
            index["attempts"][name] = {"status": "running", "started": now()}
            save(index_path, index)
            row = evaluate_case(case, condition, config, make_model(config), trigger_gate=True)
            row.update(
                comparison_identity=frozen["freeze_id"],
                evaluation_cohort=case["provenance"]["kind"],
                family=case["family"],
                category=case["category"],
                provenance=case["provenance"],
                runtime_before=before,
                runtime_after=check_runtime(model, frozen),
                resolved_config=config,
                run_id="horizontal_mixed_v1",
            )
            save(destination, row)
            index["artifact_hashes"][name] = sha(destination.read_bytes())
            index["attempts"][name].update(status="completed", ended=now())
            save(index_path, index)
            print(
                f"{position + 1}/{len(cases)} {condition} {case['id']}: {row['status']} ({row['latency']:.1f}s)",
                flush=True,
            )
    verify()
    save(
        OUTPUT / "integrity_final.json",
        {
            "verified_at": now(),
            "all_inputs_and_history_unchanged": True,
            "freeze_id": frozen["freeze_id"],
            "runtime": check_runtime(model, frozen),
            "attempt_states": dict(Counter(v["status"] for v in index["attempts"].values())),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["freeze", "run", "verify"])
    args = parser.parse_args()
    if args.stage == "freeze":
        freeze()
    elif args.stage == "run":
        run()
    else:
        verify()
        print("Frozen inputs, code, configuration and prior results unchanged")
