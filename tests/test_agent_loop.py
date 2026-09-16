import time
from functools import partial

from depguard.agent.contracts import AgentDecision, ToolCall, ToolResult, ToolSpec
from depguard.agent.loop import AgentLoop as ProductionAgentLoop
from depguard.agent.loop import build_messages
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry

# These pre-existing unit tests exercise the loop in isolation; M5 probe tests
# explicitly use the production default with capability preflight enabled.
AgentLoop = partial(ProductionAgentLoop, capability_probe=False)


class ScriptModel:
    model_name = "scripted-test-only"

    def __init__(self, actions):
        self.actions = iter(actions)

    def decide(self, messages, tools, *, timeout_seconds):
        return next(self.actions)


class SlowModel:
    model_name = "slow-test"

    def decide(self, messages, tools, *, timeout_seconds):
        time.sleep(10)


def action(name, **arguments):
    return AgentDecision("Inspect the latest evidence", ToolCall(name, arguments))


def state_at(tmp_path):
    path = tmp_path / "input.py"
    path.write_text("result = 1\n")
    return load_state(path, project_root=tmp_path)


def explode(state, args, deadline):
    raise ValueError("tool failed")


def exit_tool(state, args, deadline):
    raise SystemExit("worker exited")


def slow_tool(state, args, deadline):
    time.sleep(10)
    return ToolResult("success", "late")


def test_finish_is_required_and_cannot_claim_pass(tmp_path):
    run = AgentLoop(ScriptModel([action("finish", conclusion="PASS")]), max_steps=1).run(state_at(tmp_path), "")
    assert (run.final_status, run.termination_reason) == ("INCOMPLETE", "max_steps")
    assert run.trajectory[0].tool_result.evidence["error_code"] == "FINISH_PRECONDITION_FAILED"
    run = AgentLoop(ScriptModel([action("execute")]), max_steps=1).run(state_at(tmp_path), "")
    assert (run.final_status, run.termination_reason) == ("INCOMPLETE", "max_steps")


def test_model_can_choose_nonfixed_order_and_pass(tmp_path):
    actions = [action(name) for name in ("execute", "validate_apis", "validate_packages")]
    actions.append(action("finish", conclusion="verified"))
    run = AgentLoop(ScriptModel(actions)).run(state_at(tmp_path), "")
    assert run.final_status == "PASS"
    assert [step.tool_call.name for step in run.trajectory] == [a.tool_call.name for a in actions]


def test_protocol_recovery_and_repetition(tmp_path):
    run = AgentLoop(ScriptModel(["text", action("unknown"), "text"])).run(state_at(tmp_path), "")
    assert run.termination_reason == "protocol_errors"
    assert all(s.tool_result.evidence["kind"] == "protocol_error" for s in run.trajectory)
    run = AgentLoop(ScriptModel(["text", action("finish", conclusion="failed")])).run(
        state_at(tmp_path), "",
    )
    assert run.termination_reason == "finish"


def test_cache_and_no_progress(tmp_path):
    run = AgentLoop(ScriptModel([action("validate_packages")] * 4)).run(state_at(tmp_path), "")
    assert run.trajectory[1].tool_result.cached
    assert run.termination_reason == "no_progress"


def test_tool_exception_is_observation(tmp_path):
    registry = default_registry()
    registry.register(ToolSpec("explode", "test", {"properties": {}}), explode)
    run = AgentLoop(ScriptModel([action("explode"), action("finish", conclusion="failed")]),
                    registry=registry).run(state_at(tmp_path), "")
    assert "tool failed" in run.trajectory[0].tool_result.message
    assert run.termination_reason == "finish"


def test_worker_exit_is_tool_observation_not_model_failure(tmp_path):
    registry = default_registry()
    registry.register(ToolSpec("exit_tool", "test", {"properties": {}}), exit_tool)
    run = AgentLoop(ScriptModel([action("exit_tool"), action("finish", conclusion="failed")]),
                    registry=registry).run(state_at(tmp_path), "")
    assert run.trajectory[0].tool_result.evidence["kind"] == "tool_worker_error"
    assert run.termination_reason == "finish"


def test_deadline_covers_model_and_tools(tmp_path):
    for model, registry in [(SlowModel(), default_registry()),
                            (ScriptModel([action("slow")]), default_registry())]:
        registry.register(ToolSpec("slow", "test", {"properties": {}}), slow_tool)
        started = time.monotonic()
        run = AgentLoop(model, registry=registry, timeout_seconds=.6).run(state_at(tmp_path), "")
        assert run.termination_reason == "global_timeout"
        assert time.monotonic() - started < 4


def test_context_is_bounded_but_raw_preserved(tmp_path):
    run = AgentLoop(ScriptModel(["x" * 10000] * 3)).run(state_at(tmp_path), "")
    messages = build_messages("", state_at(tmp_path), run.trajectory, 1, 100)
    assert len(messages) == 4
    assert "TRUNCATED" in messages[-2]["content"]
    assert len(run.trajectory[0].raw_response) == 10000
