import time
from dataclasses import replace

import pytest

from depguard.agent.contracts import AgentRunResult, ToolCall, TrajectoryStep
from depguard.agent.patching import apply_patch, rollback
from depguard.agent.persistence import persist
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry


def state_at(tmp_path):
    source = tmp_path / "input.py"
    source.write_bytes(b"x = 1\ny = 3\n")
    return load_state(source, project_root=tmp_path)


def patch(state, raw):
    return apply_patch(state, {"patch": raw, "path": "input.py"}, time.monotonic()+5)


def test_context_not_line_number_and_dry_run(tmp_path):
    state = state_at(tmp_path)
    state.passed_checks["execute"] = state.version
    result = patch(state, "--- a/input.py\n+++ b/input.py\n@@ -99,2 +99,2 @@\n-x = 1\n+x = 2\n y = 3\n")
    assert result.status == "success"
    assert state.candidate_code == "x = 2\ny = 3\n"
    assert state.source_path.read_bytes() == b"x = 1\ny = 3\n"
    assert not state.passed_checks
    assert result.evidence["written"] is False


@pytest.mark.parametrize("raw", [
    "@@\n-x = 1\n+x = 2\n@@\n-z = 9\n+z = 8\n",
    "@@\n-x = 1\n+def broken(:\n",
    "@@\n+x = 2", "some prose, not a patch",
])
def test_invalid_patch_is_atomic_with_raw_error(tmp_path, raw):
    state = state_at(tmp_path)
    result = patch(state, raw)
    assert result.status == "error"
    assert result.evidence["raw_patch"] == raw
    assert result.evidence["error_line"] >= 1
    assert state.candidate_code == state.original_code


def test_ambiguous_context_is_rejected(tmp_path):
    state = state_at(tmp_path)
    state.candidate_code = "x=1\nx=1\n"
    assert patch(state, "@@\n-x=1\n+x=2").status == "error"


def test_global_memory_rollback(tmp_path):
    state = state_at(tmp_path)
    assert patch(state, "@@\n-x = 1\n+x = 2").status == "success"
    assert patch(state, "@@\n-y = 3\n+y = 4").status == "success"
    rollback(state, {}, 0)
    assert state.candidate_code == state.original_code
    assert not state.applied_patches


def passed_result(state):
    registry = default_registry()
    state.allow_test_rerun = True
    for name in state.required_checks:
        assert registry.dispatch(state, ToolCall(name), deadline=time.monotonic()+5).evidence["passed"]
    finish = registry.dispatch(state, ToolCall("finish"), deadline=time.monotonic()+5)
    trajectory = [TrajectoryStep(1, "Verified", ToolCall("finish"), finish, "utc")]
    return AgentRunResult("PASS", "finish", state.candidate_code, state.version, trajectory, {},
                          state.input_hashes, 0, "test")


def prepare_commit(tmp_path):
    state = state_at(tmp_path)
    patch(state, "@@\n-x = 1\n+x = 2")
    state.permissions.add("write_target")
    return state


def test_commit_postvalidates_and_cleans_snapshot(tmp_path):
    state = prepare_commit(tmp_path)
    result = persist(state, passed_result(state), deadline=time.monotonic()+10)
    assert result.applied
    assert state.source_path.read_text() == state.candidate_code
    assert not list(tmp_path.glob(".depguard-*"))
    assert result.persistence["post_write_checks"]["execute"]["evidence"]["passed"]


def test_no_apply_without_pass_or_permission(tmp_path):
    state = prepare_commit(tmp_path)
    result = persist(state, replace(passed_result(state), final_status="FAIL"),
                     deadline=time.monotonic()+5)
    assert not result.applied
    state.permissions.remove("write_target")
    result = persist(state, passed_result(state), deadline=time.monotonic()+5)
    assert result.rollback_result == "not_written"
    assert state.source_path.read_text() == state.original_code


def test_write_conflict_preserves_external_content(tmp_path):
    state = prepare_commit(tmp_path)
    passed = passed_result(state)
    state.source_path.write_text("external = 1\n")
    result = persist(state, passed, deadline=time.monotonic()+5)
    assert result.termination_reason == "write_failed"
    assert state.source_path.read_text() == "external = 1\n"


def test_postcheck_failure_restores_initial_bytes(tmp_path):
    state = prepare_commit(tmp_path)

    def fail(state, deadline):
        raise OSError("postcheck failed")

    result = persist(state, passed_result(state), deadline=time.monotonic()+5, validator=fail)
    assert result.rollback_result == "restored_initial"
    assert state.source_path.read_bytes() == state.original_code.encode()
    assert list(tmp_path.glob(".depguard-original-*"))


def test_atomic_write_failure_has_deterministic_result(tmp_path, monkeypatch):
    state = prepare_commit(tmp_path)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("depguard.agent.persistence._atomic_write", fail)
    result = persist(state, passed_result(state), deadline=time.monotonic()+5)
    assert result.rollback_result == "not_written"
    assert state.source_path.read_text() == state.original_code


def test_rollback_conflict_preserves_external_write_and_snapshot(tmp_path):
    state = prepare_commit(tmp_path)

    def concurrent_write(state, deadline):
        state.source_path.write_text("external = 99\n")
        raise OSError("external writer")

    result = persist(state, passed_result(state), deadline=time.monotonic()+5,
                     validator=concurrent_write)
    assert result.termination_reason == "rollback_failed"
    assert state.source_path.read_text() == "external = 99\n"
    assert list(tmp_path.glob(".depguard-original-*"))


def test_execution_rerun_requires_both_conditions(tmp_path):
    state = state_at(tmp_path)
    registry = default_registry()
    call = ToolCall("execute", {"rerun_reason": "Check nondeterminism"})
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "success"
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "denied"
    changed_args = ToolCall("execute", {"rerun_reason": "A different reason"})
    assert registry.dispatch(state, changed_args, deadline=time.monotonic()+5).status == "denied"
    state.allow_test_rerun = True
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "success"
