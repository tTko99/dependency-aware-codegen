import json
from pathlib import Path

import pytest

from depguard.agent.safety import load_state
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import (
    clean,
    freeze_config,
    host_checks,
    run_comparison,
    save,
    verify_manifest,
)
from evaluation.interview_report import report


def test_frozen_set_counts_hashes_and_provenance():
    manifest = verify_manifest(Path("data/interview_eval/manifest.json"))
    assert len(manifest["cases"]) == 24
    assert sum(c["cohort"] == "hard" for c in manifest["cases"]) == 10
    assert sum(c["is_control"] for c in manifest["cases"]) == 5
    assert all(c["provenance"]["natural_model_failure"] is False for c in manifest["cases"])


def test_new_config_freeze_preserves_case_membership(tmp_path):
    source = Path("data/interview_eval/manifest.json")
    before = source.read_bytes()
    config = tmp_path/"cloud.json"
    config.write_text(json.dumps({"provider":"cloud", "model":{"model_name":"explicit-version"}}))
    result = freeze_config(source,config,tmp_path/"manifest.json")
    assert result["cases"] == json.loads(before)["cases"] and source.read_bytes() == before
    assert verify_manifest(tmp_path/"manifest.json")["parent_manifest_sha256"] == sha(before)
    with pytest.raises(FileExistsError):
        freeze_config(source,config,tmp_path/"manifest.json")


def test_manifest_change_is_detected(tmp_path):
    source = tmp_path / "input.py"
    source.write_text("x=1")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases":[{"id":"x","code_file":str(source),"hashes":{"input.py":"bad"}}],"configs":{}}))
    with pytest.raises(ValueError, match="MANIFEST_HASH_MISMATCH"):
        verify_manifest(manifest)


def test_artifact_secret_scrubbing(tmp_path):
    secret = "test-only-sensitive-value"
    artifact = {"api_key": secret, "headers":{"Authorization":secret}, "message":"echo " + secret,
                "config":{"api_key_env":"DEEPSEEK_API_KEY"}}
    save(tmp_path / "result.json", artifact, (secret,))
    text = (tmp_path / "result.json").read_text()
    assert secret not in text and "Authorization" not in text
    assert "DEEPSEEK_API_KEY" in text
    assert str(Path.home()) not in json.dumps(clean({"path":str(Path.home())}))


def test_resume_keeps_completed_cases_on_interrupt(tmp_path, monkeypatch):
    # No real model/network: use the explicitly absent cloud credential path.
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    def interrupt(row):
        raise KeyboardInterrupt
    output = tmp_path / "run"
    args = (output, Path("data/interview_eval/manifest.json"), Path("configs/m7_cloud.json"), "one-shot")
    with pytest.raises(KeyboardInterrupt):
        run_comparison(*args, after_case=interrupt)
    first = next(output.glob("one-shot_*.json"))
    frozen = first.read_bytes()
    run_comparison(*args)
    assert first.read_bytes() == frozen and len(list(output.glob("one-shot_*.json"))) == 15
    run_comparison(output, args[1], args[2], "loop")
    summary = report(output)
    assert summary["not_run"] == {"NOT_RUN_NO_CREDENTIALS":30}
    assert summary["strict_rescue"]["rate"] is None
    assert "0/0 (N/A)" in (output/"report.md").read_text(encoding="utf-8")
    first.write_text("{}")
    with pytest.raises(ValueError, match="artifact changed"):
        run_comparison(*args)


def test_report_numbers_match_summary(tmp_path):
    from test_m7_metrics import paired
    a,b = paired()
    hashes = {}
    for name,row in [("a.json",a),("b.json",b)]:
        save(tmp_path/name,row)
        hashes[name] = sha((tmp_path/name).read_bytes())
    save(tmp_path/"run_manifest.json",{"artifact_hashes":hashes})
    summary = report(tmp_path)
    assert json.loads((tmp_path/"summary.json").read_text()) == summary
    assert "严格多轮救回 **1/1**" in (tmp_path/"report.md").read_text(encoding="utf-8")


def test_references_pass_same_host_boundary(tmp_path):
    import time
    manifest = verify_manifest(Path("data/interview_eval/manifest.json"))
    for case in manifest["cases"]:
        if case["cohort"] not in {"hard","control"}:
            continue
        source, test = tmp_path/"input.py", tmp_path/"test_input.py"
        source.write_bytes(Path(case["reference_file"]).read_bytes())
        test.write_bytes(Path(case["test_file"]).read_bytes())
        state = load_state(source,test,project_root=tmp_path)
        result = host_checks(state, time.monotonic()+15)
        assert result["host_status"] == "PASS", (case["id"],result)


def test_shared_initial_evidence_is_projected_without_granting_checks(tmp_path):
    from depguard.agent.loop import build_messages
    source = tmp_path / "input.py"
    source.write_text("value = 1\n")
    state = load_state(source, project_root=tmp_path)
    state.initial_evidence = {"host_status": "FAIL", "candidate_version": state.version,
                              "checks": {"execute": {"evidence": {"passed": False}}}}
    content = json.loads(build_messages("repair", state, [], 6, 6000)[1]["content"])
    assert content["initial_evidence"] == state.initial_evidence
    assert state.passed_checks == {}
