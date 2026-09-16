import json
import secrets
from urllib.error import HTTPError

import pytest

from depguard.agent.context import action_messages
from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.models.cloud import CloudToolCallingModel
from depguard.schemas import to_jsonable


class Response:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps({"choices": [{"message": self.message}]}).encode()


@pytest.fixture
def fake_credential(monkeypatch):
    value = secrets.token_urlsafe(32)
    monkeypatch.setenv("M5_TEST_API_KEY", value)
    return value


def make_model(transport):
    return CloudToolCallingModel("test-native-model", base_url="https://provider.example/v1",
                                 api_key_env="M5_TEST_API_KEY", transport=transport)


def test_cloud_native_tools_schema_and_observation_id(fake_credential):
    captured = []

    def transport(request, *, timeout):
        assert request.get_header("Authorization") == "Bearer " + fake_credential
        assert timeout == 7
        captured.append(json.loads(request.data))
        return Response({"content": "Check the code", "reasoning_content": "must not persist",
                         "tool_calls": [{"id": "native-1", "type": "function", "function": {
                             "name": "execute", "arguments": "{}"}}]})

    model = make_model(transport)
    decision = model.decide([], default_registry().specs, timeout_seconds=7)
    assert decision.kind == "tool_call" and decision.tool_call.call_id == "native-1"
    assert captured[0]["tools"][0]["function"]["parameters"]["type"] == "object"
    messages = action_messages(decision.tool_call, decision.thought, {"passed": False}, 1)
    model.decide(messages, default_registry().specs, timeout_seconds=7)
    assert captured[1]["messages"][-1]["tool_call_id"] == "native-1"
    assert captured[1]["messages"][-2]["tool_calls"][0]["function"]["arguments"] == "{}"
    archived = json.dumps(to_jsonable(decision))
    assert fake_credential not in archived and "must not persist" not in archived
    assert fake_credential not in repr(model.__dict__)


@pytest.mark.parametrize("content", ['{"tool": "execute"}', '```json\n{"name":"execute"}\n```'])
def test_cloud_text_json_never_becomes_native_call(fake_credential, content):
    model = make_model(lambda *args, **kwargs: Response({"content": content}))
    assert model.decide([], [], timeout_seconds=1).kind == "text"


@pytest.mark.parametrize("arguments", ["[]", "null", "invalid", '{"value": NaN}'])
def test_native_invalid_arguments_are_protocol_error(fake_credential, arguments):
    message = {"tool_calls": [{"id": "id", "function": {"name": "execute",
                                                         "arguments": arguments}}]}
    decision = make_model(lambda *a, **k: Response(message)).decide([], [], timeout_seconds=1)
    assert decision.kind == "protocol_error"
    assert decision.error_code == "invalid_arguments"


def test_multiple_native_calls_rejected(fake_credential):
    call = {"id": "id", "function": {"name": "execute", "arguments": "{}"}}
    result = make_model(lambda *a, **k: Response({"tool_calls": [call, call]})).decide(
        [], [], timeout_seconds=1)
    assert result.kind == "protocol_error" and result.tool_call is None


def test_transport_errors_are_structured_without_credentials(fake_credential):
    def failure(*args, **kwargs):
        raise HTTPError("https://provider.example", 401, fake_credential, {}, None)

    result = make_model(failure).decide([], [], timeout_seconds=1)
    assert result.kind == "provider_error" and result.error_code == "http_401"
    assert fake_credential not in json.dumps(to_jsonable(result))


def test_missing_key_never_calls_transport(monkeypatch):
    monkeypatch.delenv("M5_TEST_API_KEY", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("No network without credential")

    result = make_model(forbidden).decide([], [], timeout_seconds=1)
    assert result.error_code == "missing_api_key"


def test_echoed_credential_is_redacted(fake_credential):
    result = make_model(lambda *a, **k: Response({"content": fake_credential})).decide(
        [], [], timeout_seconds=1)
    assert fake_credential not in json.dumps(to_jsonable(result))


def test_invalid_cloud_endpoint_cannot_embed_credentials():
    with pytest.raises(ValueError):
        CloudToolCallingModel("model", base_url="https://user:password@provider.example")


def test_native_call_id_is_required(fake_credential):
    result = make_model(lambda *a, **k: Response({"tool_calls": [{"function": {
        "name": "execute", "arguments": "{}"}}]})).decide([], [], timeout_seconds=1)
    assert result.error_code == "missing_call_id"


class ProbeTransport:
    """Picklable mock HTTP transport, including tool-id round trips across the probe."""

    def __call__(self, request, *, timeout):
        payload = json.loads(request.data)
        observations = [m for m in payload["messages"] if m["role"] == "tool"]
        if not observations:
            name, arguments = "probe_echo", {"token": "start"}
        else:
            last = observations[-1]
            assert last["tool_call_id"] == f"probe-{len(observations)-1}"
            evidence = json.loads(last["content"])
            if "challenge" in evidence:
                name, arguments = "probe_echo", {"token": evidence["challenge"]}
            else:
                name, arguments = "finish", {"success": True}
        return Response({"tool_calls": [{"id": f"probe-{len(observations)}", "type": "function",
                                         "function": {"name": name,
                                                      "arguments": json.dumps(arguments)}}]})


def test_cloud_probe_reads_observations_and_finishes_with_mock_transport(fake_credential):
    result = run_probe(make_model(ProbeTransport()), default_registry().specs, use_cache=False)
    assert result.status == "passed"
    assert [row["tool_call"]["call_id"] for row in result.transcript] == [
        "probe-0", "probe-1", "probe-2",
    ]
