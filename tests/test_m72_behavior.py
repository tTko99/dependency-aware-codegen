import json
import time

import pytest

from depguard.agent.contracts import ToolCall
from depguard.agent.loop import AgentLoop
from depguard.agent.probe import run_probe
from depguard.agent.runner import run_agent, validate_candidate
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry
from depguard.agent.validation_state import validation_summary
from depguard.models.scripted import ScriptedTestModel


def state_at(tmp_path, correct=False):
    source, tests = tmp_path / "input.py", tmp_path / "test_input.py"
    source.write_text("result = 1\n")
    tests.write_text("from solution import result\ndef test_result():\n    assert result == "
                     + ("1" if correct else "2") + "\n")
    return load_state(source, tests, project_root=tmp_path)


def event(name, **arguments):
    return {"name": name, "arguments": arguments}


def invoke(state, name, **arguments):
    return default_registry().dispatch(state, ToolCall(name, arguments), deadline=time.monotonic()+15)


@pytest.mark.parametrize("kind", ["missing", "stale", "failed"])
def test_finish_preconditions_return_observation_and_continue(tmp_path, kind):
    state = state_at(tmp_path)
    state.validation_config = {"required_checks": ["run_pytest"]}
    if kind != "missing":
        invoke(state, "run_pytest")
    if kind == "stale":
        state.candidate_code = "result = 2\n"
        state.candidate_revision += 1
    actions = [event("finish", success=True), event("finish", success=False)]
    actions[1]["expect"] = {"tool": "finish", "status": "error", "contains": "FINISH_PRECONDITION_FAILED"}
    run = AgentLoop(ScriptedTestModel(actions)).run(state, "repair")
    first = run.trajectory[0]
    assert first.tool_result.evidence[f"{kind}_checks"] == ["run_pytest"]
    assert "run_pytest" in first.tool_result.evidence["allowed_next_tools"]
    assert first.observation["evidence"]["validation_state"]["required_checks"] == {"run_pytest": kind}
    assert run.termination_reason == "finish" and run.final_status == "FAIL"
    assert len(run.trajectory) == 2 and run.rejected_finish_count == 1
    assert not run.false_success


def test_rejected_finish_then_model_selects_checks_and_succeeds(tmp_path):
    state = state_at(tmp_path, correct=True)
    actions = [event("finish", success=True)] + [event(name) for name in
        ("run_pytest", "validate_packages", "execute", "validate_apis")] + [event("finish", success=True)]
    actions[1]["expect"] = {"tool": "finish", "contains": "FINISH_PRECONDITION_FAILED"}
    run = AgentLoop(ScriptedTestModel(actions)).run(state, "repair")
    assert run.final_status == "PASS" and run.termination_reason == "finish"
    assert [s.tool_call.name for s in run.trajectory] == [a["name"] for a in actions]
    assert run.rejected_finish_count == 1 and not run.false_success
    assert run.trajectory[-1].observation["evidence"]["validation_state"]["ready_to_finish_successfully"]


def test_repeated_invalid_finish_uses_no_progress_limit(tmp_path):
    run = AgentLoop(ScriptedTestModel([event("finish", success=True)]*4)).run(state_at(tmp_path), "")
    assert run.termination_reason == "no_progress" and run.final_status == "INCOMPLETE"
    assert run.trajectory[2].tool_result.evidence["kind"] == "repeat_warning"
    assert run.rejected_finish_count == 2


@pytest.mark.parametrize("arguments", [{"success": False}, {"outcome": "failure"},
    {"outcome": "abandoned"}, {"conclusion": "failed"}, {"success": False, "conclusion": "PASS"}])
def test_explicit_failure_terminates_even_with_passing_evidence(tmp_path, arguments):
    state = state_at(tmp_path, correct=True)
    validate_candidate(state, time.monotonic()+15)
    run = AgentLoop(ScriptedTestModel([event("finish", **arguments)])).run(state, "")
    assert run.final_status == "FAIL" and run.termination_reason == "finish"
    assert not run.false_success and run.rejected_finish_count == 0


def test_patch_preserves_stale_history_without_reusing_passes(tmp_path):
    state = state_at(tmp_path, correct=True)
    validate_candidate(state, time.monotonic()+15)
    old = state.version
    result = invoke(state, "apply_patch", patch="--- a/input.py\n+++ b/input.py\n@@\n-result = 1\n+result = 2\n")
    assert result.status == "success" and state.version != old
    assert state.candidate_revision == 1 and state.passed_checks == {}
    summary = result.evidence["validation_state"]
    assert set(summary["required_checks"].values()) == {"stale"}
    assert not summary["ready_to_finish_successfully"]
    rejected = invoke(state, "finish", success=True)
    assert set(rejected.evidence["stale_checks"]) == state.required_checks
    invoke(state, "run_pytest")
    assert validation_summary(state)["required_checks"]["run_pytest"] == "failed"
    assert state.source_path.read_text() == "result = 1\n"


class ForbiddenModel:
    model_name = "must-not-be-called"

    def decide(self, *args, **kwargs):
        raise AssertionError("Control must never invoke a model, including probe")


def test_correct_control_trigger_gate_skips_model_and_patch(tmp_path):
    state = state_at(tmp_path, correct=True)
    before = (state.source_path.read_bytes(), state.test_path.read_bytes())
    result = run_agent(AgentLoop(ForbiddenModel()), state, "keep correct code")
    assert result.final_status == "NO_REPAIR_NEEDED" and not result.agent_invoked
    assert result.termination_reason == "no_repair_needed" and result.trajectory == []
    assert not state.applied_patches and state.candidate_revision == 0
    assert before == (state.source_path.read_bytes(), state.test_path.read_bytes())
    assert result.initial_verification["host_status"] == "PASS"


def test_bad_candidate_triggers_model_and_probe_stays_independent(tmp_path):
    model = ScriptedTestModel([event("finish", success=False)])
    assert run_probe(model, default_registry().specs, use_cache=False).status == "passed"
    assert model.index == 0
    result = run_agent(AgentLoop(model), state_at(tmp_path), "repair")
    assert result.agent_invoked and result.final_status == "FAIL"
    assert result.capability_probe["status"] == "passed"
    assert result.initial_verification["host_status"] == "FAIL"


def test_validation_summary_survives_bounded_observation(tmp_path):
    from depguard.agent.context import compact_observation
    state = state_at(tmp_path)
    result = invoke(state, "run_pytest")
    observation = compact_observation(result, 1200)
    assert len(json.dumps(observation)) <= 1200
    assert observation["evidence"]["validation_state"]["required_checks"]["run_pytest"] == "failed"


def test_evaluation_control_has_zero_calls_and_same_host_evidence(tmp_path):
    from evaluation.interview_benchmark import evaluate_case
    from evaluation.interview_metrics import real_pass, validation_counts
    state = state_at(tmp_path, correct=True)
    case = {"id": "correct", "cohort": "control", "is_control": True,
            "code_file": str(state.source_path), "test_file": str(state.test_path),
            "required_checks": sorted(state.required_checks), "requirement": "Return one"}
    config = {"execution_timeout_seconds": 10, "shared_initial_evidence": True,
              "agent": {"timeout_seconds": 30, "recent_steps": 6, "output_limit": 4000}}
    row = evaluate_case(case, "loop", config, ForbiddenModel(), trigger_gate=True)
    assert row["status"] == "NO_REPAIR_NEEDED" and not row["agent_invoked"]
    assert row["model_calls"] == row["patch_count"] == 0
    assert row["final_verification"] == row["initial_verification"]
    assert real_pass(row) and validation_counts(row)["total"] == 4
