"""Single frozen M7.2 retest. Reuse every M7.1 one-shot result byte for byte."""
import argparse
import json
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import (
    make_model,
    run_comparison,
    save,
    start_run,
    verify_manifest,
)
from evaluation.interview_report import load_rows

BEFORE = Path("results/qwen3_validation")
MANIFEST = BEFORE / "frozen/manifest.json"
CONFIG = Path("configs/m7_qwen3_30b.json")


def protected_hashes():
    manifest = verify_manifest(MANIFEST)
    paths = {MANIFEST, CONFIG, Path("data/interview_eval/manifest.json"), Path("evaluation/interview_metrics.py")}
    for case in manifest["cases"]:
        paths.update(Path(case["code_file"]).parent / name for name in case["hashes"])
    paths.update(p for p in BEFORE.rglob("*") if p.is_file())
    return {p.as_posix(): sha(p.read_bytes()) for p in sorted(paths)}


def run(root):
    protected = root / "protected_before.json"
    if protected.exists():
        assert json.loads(protected.read_text()) == protected_hashes(), "Protected evidence changed"
    else:
        save(protected, protected_hashes())
    old = json.loads((BEFORE / "existing/run_manifest.json").read_text())
    config = json.loads(CONFIG.read_text())
    model = make_model(config)
    runtime = model.runtime_metadata()
    assert runtime["installed_model"]["digest"] == old["model_digest"], "Model digest changed"
    assert runtime["ollama_version"] == old["ollama_version"], "Ollama version changed"
    assert config == old["resolved_config"], "Frozen configuration changed"
    probe_path = root / "capability_probe.json"
    if not probe_path.exists():
        probe = to_jsonable(run_probe(model, default_registry().specs,
            timeout_seconds=config["agent"]["probe_timeout"], use_cache=False))
        save(probe_path, {"config": config, "runtime_before": runtime,
                          "runtime_after": model.runtime_metadata(), "result": probe})
    else:
        probe = json.loads(probe_path.read_text())["result"]
    if probe["status"] != "passed":
        raise RuntimeError("Full native capability probe failed; no formal run started")
    resident = model.runtime_metadata()
    assert resident["runtime"]["context_length"] == 16384, "Unexpected loaded context"
    save(root / "resolved_config.json", config)
    comparison = root / "comparison"
    _, _, index = start_run(comparison, MANIFEST, CONFIG)
    assert index["comparison_identity"] == old["comparison_identity"]
    implementation = {p.as_posix(): sha(p.read_bytes()) for p in sorted(
        list(Path("src/depguard").rglob("*.py")) + [Path("evaluation/interview_benchmark.py"),
        Path("evaluation/m72_validation.py")])}
    if "implementation_sha256" in index:
        assert index["implementation_sha256"] == implementation, "Implementation changed during run"
    index["implementation_sha256"] = implementation
    load_rows(BEFORE / "existing")  # Verify all source artifacts before reusing baseline.
    for name, expected in old["artifact_hashes"].items():
        if not name.startswith("one-shot_"):
            continue
        path = comparison / name
        original = (BEFORE / "existing" / name).read_bytes()
        if path.exists():
            assert path.read_bytes() == original
        else:
            path.write_bytes(original)
        index["artifact_hashes"][name] = expected
    index["behavior_revision"] = "M7.2"
    index["baseline_reused_from"] = (BEFORE / "existing/run_manifest.json").as_posix()
    index["source_manifest"] = MANIFEST.as_posix()
    save(comparison / "run_manifest.json", index)
    run_comparison(comparison, MANIFEST, CONFIG, "loop", trigger_gate=True)
    assert json.loads(protected.read_text()) == protected_hashes(), "Protected evidence changed"
    save(root / "runtime_after.json", model.runtime_metadata())
    print("M7.2 complete; original baseline, cases, configs and M7.1 artifacts unchanged", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="results/m72")
    run(Path(parser.parse_args().output_dir))
