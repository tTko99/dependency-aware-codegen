"""Native Chat Completions tool calling using stdlib HTTP and environment credentials.

Compatible with the DeepSeek non-thinking tool protocol. No SDK dependency and no
credentials stored on the model object (which crosses the worker-process boundary).
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from depguard.agent.contracts import AgentDecision
from depguard.models.tool_protocol import native_decision, provider_tools


class CloudToolCallingModel:
    provider = "cloud"
    one_shot_supported = False

    def __init__(self, model_name, *, base_url="https://api.deepseek.com",
                 api_key_env="DEEPSEEK_API_KEY", max_new_tokens=1024, temperature=0.0,
                 transport=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Cloud base_url must be HTTPS without credentials, query or fragment")
        if not model_name or max_new_tokens <= 0 or not api_key_env.isidentifier():
            raise ValueError("Invalid model, token limit or environment variable name")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.transport = transport

    def probe_identity(self):
        return {"provider": self.provider, "model": self.model_name, "endpoint": self.base_url,
                "max_new_tokens": self.max_new_tokens, "temperature": self.temperature}

    def decide(self, messages, tools, *, timeout_seconds):
        key = os.environ.get(self.api_key_env)
        if not key:
            return AgentDecision(kind="provider_error", error_code="missing_api_key",
                                 message="Cloud API key environment variable is not set")
        try:
            payload = {"model": self.model_name, "messages": cloud_messages(messages),
                       "tools": provider_tools(tools), "tool_choice": "auto", "stream": False,
                       "max_tokens": self.max_new_tokens, "temperature": self.temperature}
            if not tools:  # Same-provider one-shot evaluation uses a text completion.
                payload.pop("tools")
                payload.pop("tool_choice")
            if urlsplit(self.base_url).hostname == "api.deepseek.com":
                # Thinking-mode continuation can require retaining provider reasoning.
                # This agent contract deliberately supports the non-thinking protocol.
                payload["thinking"] = {"type": "disabled"}
            request = Request(self.base_url + "/chat/completions",
                              data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json",
                                       "Authorization": "Bearer " + key}, method="POST")
            with (self.transport or urlopen)(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices") if isinstance(body, dict) else None
            if not isinstance(choices, list) or len(choices) != 1:
                return AgentDecision(kind="protocol_error", error_code="invalid_choices",
                                     message="Provider must return exactly one completion")
            decision = native_decision(choices[0].get("message"), string_arguments=True,
                                       require_call_id=True)
            if isinstance(decision.raw_response, dict):
                usage = {k: v for k, v in (body.get("usage") or {}).items()
                    if k in {"prompt_tokens", "completion_tokens", "total_tokens"}
                    and isinstance(v, (int, float))}
                if usage:
                    decision.raw_response["usage"] = usage
                if isinstance(body.get("model"), str):
                    decision.raw_response["provider_model"] = body["model"]
            # Redact the actual credential even if a provider erroneously echoes it.
            return _redact_decision(decision, key)
        except HTTPError as exc:
            return AgentDecision(kind="provider_error", error_code=f"http_{exc.code}",
                                 message="Cloud HTTP request failed")
        except Exception as exc:  # noqa: BLE001 - never expose request/header/body in errors
            return AgentDecision(kind="provider_error", error_code=type(exc).__name__,
                                 message="Cloud request or response failed")


def cloud_messages(messages):
    converted = []
    for message in messages:
        item = {k: v for k, v in message.items() if k != "tool_name"}
        if message.get("tool_calls"):
            item["tool_calls"] = [{"id": call["id"], "type": "function", "function": {
                "name": call["function"]["name"],
                "arguments": json.dumps(call["function"]["arguments"]),
            }} for call in message["tool_calls"]]
        converted.append(item)
    return converted


def _redact_decision(decision, secret):
    from dataclasses import replace

    from depguard.schemas import to_jsonable

    def redact(value):
        if isinstance(value, str):
            return value.replace(secret, "[REDACTED]")
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    raw = redact(to_jsonable(decision.raw_response))
    call = decision.tool_call
    if call:
        arguments = redact(call.arguments)
        call = replace(call, name=call.name.replace(secret, "[REDACTED]"), arguments=arguments,
                       call_id=call.call_id.replace(secret, "[REDACTED]"))
    return replace(decision, thought=decision.thought.replace(secret, "[REDACTED]"),
                   raw_response=raw, tool_call=call)
