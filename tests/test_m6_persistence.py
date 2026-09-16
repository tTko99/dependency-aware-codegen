import time
from dataclasses import replace

import pytest

from depguard.agent.contracts import AgentRunResult, ToolCall, TrajectoryStep
from depguard.agent.patching import apply_patch
from depguard.agent.persistence import persist
from depguard.agent.safety import load_state, sha256_file
from depguard.agent.tools import default_registry


def prepared(tmp_path):
    source = tmp_path / "input.py"
    source.write_bytes(b"result = 1\r\n")
    state = load_state(source, project_root=tmp_path)
    state.permissions.add("write_target")
    assert apply_patch(state, {"path": "input.py", "patch": "@@\n-result = 1\n+result = 2"},
                       0).status == "success"
    registry = default_registry()
    for name in state.required_checks:
        assert registry.dispatch(state, ToolCall(name), deadline=time.monotonic()+5).evidence["passed"]
    finish = registry.dispatch(state, ToolCall("finish"), deadline=time.monotonic()+5)
    run = AgentRunResult("PASS", "finish", state.candidate_code, state.version,
                         [TrajectoryStep(1, "verified", ToolCall("finish"), finish, "utc")],
                         dict(state.passed_checks), dict(state.input_hashes), 0, "test")
    return state, run


def test_success_apply_preserves_crlf_and_cleans_snapshot(tmp_path):
    state, run = prepared(tmp_path)
    result = persist(state, run, deadline=time.monotonic()+10)
    assert result.applied and state.source_path.read_bytes() == b"result = 2\r\n"
    assert result.persistence["snapshot_cleaned"] and not list(tmp_path.glob(".depguard-*"))


@pytest.mark.parametrize("condition", ["fail", "stale", "forged", "scope", "permission"])
def test_apply_requires_fresh_complete_host_evidence(tmp_path, condition):
    state, run = prepared(tmp_path)
    if condition == "fail":
        run = replace(run, final_status="FAIL")
    elif condition == "stale":
        state.candidate_revision += 1
    elif condition == "forged":
        run = replace(run, trajectory=[])
    elif condition == "scope":
        state.write_scope.clear()
    else:
        state.permissions.remove("write_target")
    result = persist(state, run, deadline=time.monotonic()+5)
    assert not result.applied and state.source_path.read_bytes() == b"result = 1\r\n"
    assert not list(tmp_path.glob(".depguard-*"))


def test_external_source_conflict_reports_code(tmp_path):
    state, run = prepared(tmp_path)
    state.source_path.write_text("user = 99\n")
    result = persist(state, run, deadline=time.monotonic()+5)
    assert result.persistence["refusal"]["evidence"]["error_code"] == "SOURCE_INTEGRITY_MISMATCH"
    assert state.source_path.read_text() == "user = 99\n"


@pytest.mark.parametrize("failure", ["write", "replace", "postcheck", "missing_evidence"])
def test_failure_has_structured_successful_rollback(tmp_path, monkeypatch, failure):
    state, run = prepared(tmp_path)
    before = sha256_file(state.source_path)

    def fail(*args, **kwargs):
        raise OSError("injected failure")

    options = {}
    if failure == "write":
        monkeypatch.setattr("depguard.agent.persistence._atomic_write", fail)
    elif failure == "replace":
        monkeypatch.setattr("depguard.agent.persistence.os.replace", fail)
    elif failure == "missing_evidence":
        options["validator"] = lambda *args: {}
    else:
        options["validator"] = fail
    result = persist(state, run, deadline=time.monotonic()+5, **options)
    rollback = result.persistence["rollback"]
    assert rollback["attempted"] and rollback["succeeded"] and rollback["failure_reason"] is None
    assert rollback["restored_sha256"] == before == sha256_file(state.source_path)
    assert not result.applied and result.termination_reason == "write_failed"
    assert list(tmp_path.glob(".depguard-original-*.bak"))
    assert not list(tmp_path.glob(".depguard-write-*"))


def test_rollback_failure_preserves_recovery_snapshot(tmp_path, monkeypatch):
    state, run = prepared(tmp_path)

    def postcheck(state, deadline):
        def refuse(*args):
            raise OSError("restore device unavailable")
        monkeypatch.setattr("depguard.agent.persistence._atomic_write", refuse)
        raise OSError("postcheck failed")

    result = persist(state, run, deadline=time.monotonic()+5, validator=postcheck)
    assert result.termination_reason == "rollback_failed"
    rollback = result.persistence["rollback"]
    assert rollback["attempted"] and not rollback["succeeded"] and rollback["failure_reason"]
    assert result.persistence["recovery_path"] and list(tmp_path.glob(".depguard-original-*"))


def test_postwrite_concurrent_modification_is_preserved(tmp_path):
    state, run = prepared(tmp_path)

    def external(state, deadline):
        state.source_path.write_text("user = 99\n")
        return {}

    result = persist(state, run, deadline=time.monotonic()+5, validator=external)
    assert result.termination_reason == "rollback_failed"
    assert state.source_path.read_text() == "user = 99\n"
    assert result.persistence["recovery_path"]


def test_interruption_after_write_restores_original(tmp_path):
    state, run = prepared(tmp_path)
    def interrupted(*args):
        raise KeyboardInterrupt("injected interruption")
    result = persist(state, run, deadline=time.monotonic()+5, validator=interrupted)
    assert result.persistence["rollback"]["succeeded"]
    assert state.source_path.read_bytes() == b"result = 1\r\n"
