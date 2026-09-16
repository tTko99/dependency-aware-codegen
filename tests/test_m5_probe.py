import copy

import pytest

from depguard.agent.loop import AgentLoop
from depguard.agent.probe import clear_probe_cache, run_probe
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry
from depguard.models.scripted import ScriptedTestModel


@pytest.fixture(autouse=True)
def empty_cache():
    clear_probe_cache()
    yield
    clear_probe_cache()


def probe(actions=None):
    return run_probe(ScriptedTestModel([], probe_actions=actions), default_registry().specs)


def test_probe_success_and_no_official_state_mutation(tmp_path):
    source = tmp_path / "input.py"
    source.write_text("result=1\n")
    state = load_state(source, project_root=tmp_path)
    before = copy.deepcopy(state)
    model = ScriptedTestModel([])
    result = run_probe(model, default_registry().specs)
    assert result.status == "passed"
    assert result.termination_reason == "finish"
    assert result.transcript[-1]["observation"]["finished"] is True
    assert result.transcript[-1]["termination_reason"] == "finish"
    assert [step["stage"] for step in result.transcript] == [
        "first_call", "observation_followup", "finish",
    ]
    assert model.index == model.probe_index == 0
    assert state == before
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("event,kind", [
    ({"kind": "text", "message": "hello"}, "text"),
    ({"name": "probe_echo", "arguments": "{}"}, "protocol_error"),
    ({"name": "probe_echo", "arguments": {"token": 2}}, "protocol_error"),
    ({"name": "unknown", "arguments": {}}, "protocol_error"),
    ({"kind": "multiple_calls"}, "protocol_error"),
    ({"kind": "provider_error", "error_code": "outage"}, "provider_error"),
])
def test_probe_rejects_invalid_first_action(event, kind):
    result = probe([event])
    assert (result.status, result.stage, result.model_response_kind) == ("failed", "first_call", kind)


def test_probe_requires_reading_new_observation():
    result = probe([{"name": "probe_echo", "arguments": {"token": "start"}}] * 2)
    assert result.stage == "observation_followup"
    assert result.status == "failed"


def test_probe_requires_finish():
    result = probe([{"name": "probe_echo", "arguments": {"token": "start"}},
                    {"name": "probe_echo", "arguments": {"token": "$challenge"}},
                    {"kind": "text", "message": "done"}])
    assert (result.status, result.stage) == ("failed", "finish")


def test_failed_probe_never_enters_loop(tmp_path):
    source = tmp_path / "input.py"
    source.write_text("result=1\n")
    state = load_state(source, project_root=tmp_path)
    before = copy.deepcopy(state)
    model = ScriptedTestModel([{"name": "apply_patch", "arguments": {"patch": "bad"}}],
                              probe_actions=[{"kind": "text"}])
    run = AgentLoop(model).run(state, "test")
    assert run.termination_reason == "MODEL_TOOL_PROTOCOL_UNSUPPORTED"
    assert run.final_status == "FAIL"
    assert run.trajectory == [] and model.index == 0
    assert state == before
    assert run.capabilities["native_tool_calling"] == "unsupported"


def test_cache_can_disable_clear_and_keys_include_schema():
    model = ScriptedTestModel([])
    specs = default_registry().specs
    assert not run_probe(model, specs).cached
    assert run_probe(model, specs).cached
    assert not run_probe(model, specs, use_cache=False).cached
    assert not run_probe(model, specs[:-1]).cached
    clear_probe_cache()
    assert not run_probe(model, specs).cached
