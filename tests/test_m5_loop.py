import json
import time
from pathlib import Path

import pytest

from depguard.agent.context import compact_observation
from depguard.agent.contracts import ToolCall, ToolResult, ToolSpec
from depguard.agent.loop import AgentLoop, build_messages
from depguard.agent.safety import load_state
from depguard.agent.tools import action_fingerprint, default_registry
from depguard.models.scripted import ScriptedTestModel


def state_at(tmp_path):
    source = tmp_path / "input.py"
    tests = tmp_path / "test_input.py"
    source.write_text("result = 1\n")
    tests.write_text("from solution import result\ndef test_result():\n    assert result == 3\n")
    return load_state(source, tests, project_root=tmp_path)


def multiround_script():
    actions = json.loads(Path("examples/m5/script.json").read_text())["actions"]
    for action in actions:
        if action["name"] == "apply_patch":
            action["arguments"]["patch"] = action["arguments"]["patch"].replace("examples/m5/", "")
    return actions


def test_two_repairs_real_pytest_and_host_pass(tmp_path):
    state = state_at(tmp_path)
    original = state.source_path.read_bytes()
    model = ScriptedTestModel(multiround_script())
    run = AgentLoop(model, recent_steps=2).run(state, "Return three as result")
    assert run.capability_probe["status"] == "passed"
    assert run.final_status == "PASS" and run.termination_reason == "finish"
    tests = [s for s in run.trajectory if s.tool_call and s.tool_call.name == "run_pytest"]
    assert [s.tool_result.evidence["passed"] for s in tests] == [False, False, True]
    assert len({s.candidate_version for s in tests}) == 3
    assert len(state.applied_patches) == 2 and not run.false_success
    assert state.source_path.read_bytes() == original
    assert all(s.raw_result_ref and s.state_transition and s.observation for s in run.trajectory)
    assert len(state.raw_results) == len(run.trajectory) == 9
    messages = build_messages("Return three", state, run.trajectory, 2, 4000)
    projected = json.loads(messages[1]["content"])
    assert projected["older_steps_summary"]["steps"] == 7
    assert projected["older_steps_summary"]["patch_count"] == 2
    assert len(messages) == 2 + 2*2


def test_script_really_requires_updated_observation():
    model = ScriptedTestModel([{"name": "finish", "expect": {"tool": "run_pytest", "passed": True}}])
    result = model.decide([{"role": "tool", "tool_name": "run_pytest", "content": json.dumps({
        "evidence": {"passed": False}})}], [], timeout_seconds=1)
    assert result.error_code == "observation_mismatch"


def test_text_recovery_and_false_success(tmp_path):
    model = ScriptedTestModel([{"kind": "text", "message": '{"tool":"finish"}'},
                               {"name": "finish", "arguments": {"success": True}}])
    run = AgentLoop(model, max_steps=2).run(state_at(tmp_path), "")
    assert run.termination_reason == "max_steps" and run.final_status == "INCOMPLETE"
    assert run.rejected_finish_count == 1
    assert run.finish_verification["missing_checks"]
    assert run.trajectory[0].tool_call is None
    assert run.trajectory[0].tool_result.evidence["kind"] == "protocol_error"


@pytest.mark.parametrize("event", [
    {"kind": "text"}, {"kind": "multiple_calls"},
    {"name": "execute", "arguments": "{}"}, {"name": "not_registered"},
    {"name": "finish", "arguments": {"success": "true"}},
])
def test_protocol_error_limit_is_configurable(tmp_path, event):
    run = AgentLoop(ScriptedTestModel([event]*2), protocol_limit=2).run(state_at(tmp_path), "")
    assert run.termination_reason == "protocol_errors" and len(run.trajectory) == 2


def test_provider_failure_is_distinct_from_protocol_limit(tmp_path):
    model = ScriptedTestModel([{"kind": "provider_error", "error_code": "unavailable"}])
    run = AgentLoop(model).run(state_at(tmp_path), "")
    assert (run.final_status, run.termination_reason) == ("ERROR", "model_error")
    assert run.trajectory[0].tool_result.evidence["error_code"] == "unavailable"


def test_repeated_action_warns_before_termination(tmp_path):
    run = AgentLoop(ScriptedTestModel([{"name": "validate_packages"}]*4)).run(state_at(tmp_path), "")
    assert run.trajectory[1].cached
    assert run.trajectory[2].tool_result.evidence["kind"] == "repeat_warning"
    assert run.termination_reason == "no_progress"


def test_fingerprint_canonical_parameters_and_config_version(tmp_path):
    state = state_at(tmp_path)
    first = ToolCall("finish", {"success": True, "conclusion": "pass"})
    second = ToolCall("finish", {"conclusion": "pass", "success": True}, call_id="different-id")
    original = action_fingerprint(state, first)
    assert original == action_fingerprint(state, second)
    state.validation_config["revision"] = 2
    assert original != action_fingerprint(state, first)


def test_execution_can_rerun_when_config_or_candidate_changes(tmp_path):
    state = state_at(tmp_path)
    registry = default_registry()
    call = ToolCall("run_pytest")
    invoke = lambda: registry.dispatch(state, call, deadline=time.monotonic()+10)
    assert invoke().status == "success"
    assert invoke().status == "denied"
    state.validation_config["revision"] = 2
    assert invoke().status == "success"
    state.candidate_code = "result = 3\n"
    assert invoke().evidence["passed"]
    state.allow_test_rerun = True
    assert invoke().status == "success"


def transient_execution(state, args, deadline):
    if not state.last_execution_results:
        raise OSError("Temporary test runner infrastructure failure")
    return ToolResult("success", "Recovered runner", {"passed": True})


def test_infrastructure_error_allows_retry_without_rerun_flag(tmp_path):
    registry = default_registry()
    spec, _ = registry.entries["execute"]
    registry.entries["execute"] = (spec, transient_execution)
    model = ScriptedTestModel([{"name": "execute"},
                               {"name": "execute", "expect": {"tool": "execute", "status": "error"}},
                               {"name": "finish", "arguments": {"success": True}}])
    state = state_at(tmp_path)
    state.validation_config = {"required_checks": ["execute"]}
    run = AgentLoop(model, registry=registry).run(state, "")
    assert run.trajectory[0].tool_result.status == "error"
    assert run.trajectory[1].tool_result.evidence["passed"] is True
    assert run.final_status == "PASS"


def test_finish_rejects_stale_validation_config(tmp_path):
    state = state_at(tmp_path)
    state.validation_config = {"required_checks": ["validate_packages"]}
    registry = default_registry()
    registry.dispatch(state, ToolCall("validate_packages"), deadline=time.monotonic()+5)
    state.validation_config["revision"] = 2
    run = AgentLoop(ScriptedTestModel([{"name": "finish", "arguments": {"success": True}}]), max_steps=1).run(
        state, "")
    assert run.final_status == "INCOMPLETE" and run.rejected_finish_count == 1
    assert run.trajectory[-1].tool_result.evidence["stale_checks"] == ["validate_packages"]


def test_finish_rejects_checks_invalidated_by_patch(tmp_path):
    state = state_at(tmp_path)
    state.validation_config = {"required_checks": ["validate_packages"]}
    actions = [{"name": "validate_packages"}, {"name": "apply_patch", "arguments": {
        "patch": "@@\n-result = 1\n+result = 2\n", "path": "input.py"}},
        {"name": "finish", "arguments": {"success": True}}]
    run = AgentLoop(ScriptedTestModel(actions), max_steps=3).run(state, "")
    assert run.final_status == "INCOMPLETE" and run.rejected_finish_count == 1
    assert run.trajectory[-1].tool_result.evidence["stale_checks"] == ["validate_packages"]


def huge_output(state, args, deadline):
    return ToolResult("success", "Test failed", {"passed": False, "execution": {
        "stdout": "HEADER\n" + "x"*30000 + "\nFAILED test_result: AssertionError at input.py:1",
        "stderr": "", "error_type": "AssertionError"}})


def test_observation_budget_preserves_raw_failure_and_tail(tmp_path):
    registry = default_registry()
    registry.register(ToolSpec("verbose", "test output", {"properties": {}}), huge_output)
    run = AgentLoop(ScriptedTestModel([{"name": "verbose"}, {"name": "finish"}]),
                    registry=registry, output_limit=1200).run(state_at(tmp_path), "")
    step = run.trajectory[0]
    assert len(json.dumps(step.observation)) <= 1200
    assert step.observation["truncated"]
    assert "test_result" in json.dumps(step.observation)
    assert len(step.tool_result.evidence["execution"]["stdout"]) > 30000
    for limit in (80, 100, 500, 4000):
        assert len(json.dumps(compact_observation(step.tool_result, limit))) <= limit


def test_max_steps_distinct_after_successful_probe(tmp_path):
    run = AgentLoop(ScriptedTestModel([{"name": "validate_packages"}]), max_steps=1).run(
        state_at(tmp_path), "")
    assert run.termination_reason == "max_steps"
    assert run.capability_probe["status"] == "passed" and len(run.trajectory) == 1
