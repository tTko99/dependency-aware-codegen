import json

import pytest

from depguard.agent.context import action_messages
from depguard.agent.contracts import AgentDecision
from depguard.agent.tools import default_registry
from depguard.models.agent import OllamaAgentModel


def test_agent_adapter_has_same_options_and_one_action(monkeypatch):
    captured = {}

    def request(self, path, payload):
        captured.update(payload)
        return {"message": {"content": "Check current API findings", "thinking": "hidden",
                "tool_calls": [{"function": {"name": "validate_apis", "arguments": {}}}]}}

    monkeypatch.setattr(OllamaAgentModel, "_post_json", request)
    model = OllamaAgentModel("qwen2.5-coder:7b", max_new_tokens=256, context_length=4096)
    result = model.decide([{"role": "user", "content": "input"}], default_registry().specs,
                          timeout_seconds=7)
    assert isinstance(result, AgentDecision)
    assert result.tool_call.name == "validate_apis"
    assert captured["options"]["num_predict"] == 256
    assert captured["options"]["seed"] == 42
    assert model.timeout_seconds == 7
    assert captured["tools"][0]["type"] == "function"
    assert "thinking" not in result.raw_response


def test_text_is_returned_for_host_protocol_observation(monkeypatch):
    monkeypatch.setattr(OllamaAgentModel, "_post_json",
                        lambda *args: {"message": {"content": "plain text"}})
    result = OllamaAgentModel("qwen2.5-coder:7b").decide([], [], timeout_seconds=1)
    assert result.kind == "text"
    assert result.raw_response == {"content": "plain text"}


def test_json_text_is_not_a_native_tool_call(monkeypatch):
    content = json.dumps({"thought": "test", "tool_call": {"name": "execute", "arguments": {}}})
    monkeypatch.setattr(OllamaAgentModel, "_post_json",
                        lambda *args: {"message": {"content": content}})
    result = OllamaAgentModel("qwen2.5-coder:7b").decide([], [], timeout_seconds=1)
    assert result.kind == "text"


@pytest.mark.parametrize("arguments", [{"success": True}, '{"success":true}'])
def test_ollama_native_roundtrip_and_request_contract(monkeypatch, arguments):
    captured = {}

    def request(self, path, payload):
        assert path == "/api/chat"
        captured.update(payload)
        return {"model": "qwen3-coder:30b", "message": {"content": "", "thinking": "secret",
            "tool_calls": [{"id": "call-42", "function": {
                "index": 0, "name": "finish", "arguments": arguments}}]}}

    monkeypatch.setattr(OllamaAgentModel, "_post_json", request)
    model = OllamaAgentModel("qwen3-coder:30b", context_length=16384,
                             temperature=0, keep_alive="10m")
    decision = model.decide([], default_registry().specs, timeout_seconds=5)
    assert decision.kind == "tool_call"
    assert decision.tool_call.arguments == {"success": True}
    messages = action_messages(decision.tool_call, "Selected finish", {"passed": True}, 1)
    model.decide(messages, default_registry().specs, timeout_seconds=5)
    assert captured["messages"][1]["role"] == "tool"
    assert captured["messages"][1]["tool_name"] == "finish"
    assert captured["messages"][1]["tool_call_id"] == "call-42"
    assert captured["messages"][0]["tool_calls"][0]["function"]["index"] == 0
    assert captured["stream"] is False and captured["keep_alive"] == "10m"
    assert captured["options"]["num_ctx"] == 16384
    assert captured["options"]["temperature"] == 0
    assert decision.raw_response["provider_model"] == "qwen3-coder:30b"
    assert "secret" not in json.dumps(decision.raw_response)


@pytest.mark.parametrize("arguments", ['[]', '{bad}', '{"x":NaN}'])
def test_ollama_invalid_native_arguments_rejected(monkeypatch, arguments):
    monkeypatch.setattr(OllamaAgentModel, "_post_json", lambda *a: {"message": {
        "tool_calls": [{"function": {"name": "execute", "arguments": arguments}}]}})
    result = OllamaAgentModel("local").decide([], [], timeout_seconds=1)
    assert result.kind == "protocol_error"
    assert result.error_code == "invalid_arguments"
