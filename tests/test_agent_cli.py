import json

import pytest

from depguard import cli
from depguard.agent.contracts import AgentDecision, ToolCall


class RepairScript:
    model_name = "test-only"

    def __init__(self):
        self.index = 0

    def decide(self, messages, tools, *, timeout_seconds):
        actions = [
            ToolCall("run_pytest"),
            ToolCall("apply_patch", {"patch": "@@\n-result=1\n+result=2\n", "path": "input.py"}),
            ToolCall("validate_packages"), ToolCall("validate_apis"),
            ToolCall("execute"), ToolCall("run_pytest"),
            ToolCall("finish", {"conclusion": "Tests and checks passed"}),
        ]
        action = actions[self.index]
        self.index += 1
        return AgentDecision("Use the latest test evidence", action)


@pytest.mark.parametrize("apply", [False, True])
def test_agent_cli_real_checks_dry_run_and_apply(tmp_path, monkeypatch, capsys, apply):
    source, test = tmp_path / "input.py", tmp_path / "test_input.py"
    source.write_bytes(b"result=1\n")
    test.write_text("from solution import result\ndef test_result():\n    assert result == 2\n")
    test_bytes = test.read_bytes()
    monkeypatch.setattr("depguard.models.agent.OllamaAgentModel", lambda **kwargs: RepairScript())
    args = ["agent", "--code-file", str(source), "--test-file", str(test),
            "--project-root", str(tmp_path), "--timeout", "30", "--no-capability-probe"]
    if apply:
        args.append("--apply")
    assert cli.main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["final_status"] == "PASS"
    assert payload["termination_reason"] == "finish"
    assert payload["applied"] == apply
    assert source.read_bytes() == (b"result=2\n" if apply else b"result=1\n")
    assert test.read_bytes() == test_bytes
    assert payload["trajectory"][0]["tool_result"]["evidence"]["passed"] is False
