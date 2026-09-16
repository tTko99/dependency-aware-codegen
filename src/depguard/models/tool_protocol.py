"""Native provider messages only. Content is never parsed as a tool call."""
from __future__ import annotations

import json

from depguard.agent.contracts import AgentDecision, ToolCall


def native_decision(message, *, string_arguments=False, require_call_id=False):
    if not isinstance(message, dict):
        return AgentDecision(kind="protocol_error", error_code="invalid_message",
                             message="Provider message must be an object")
    public = {key: message[key] for key in ("content", "tool_calls") if key in message}
    calls = message.get("tool_calls")
    if calls is None or calls == []:
        return AgentDecision(kind="text", raw_response=public,
                             message="Text is not a native tool call")
    if not isinstance(calls, list) or len(calls) != 1:
        return AgentDecision(kind="protocol_error", error_code="multiple_or_invalid_calls",
                             message="Exactly one native tool call is required", raw_response=public)
    call = calls[0]
    function = call.get("function") if isinstance(call, dict) else None
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        return AgentDecision(kind="protocol_error", error_code="invalid_function",
                             message="Native call has no valid function", raw_response=public)
    arguments = function.get("arguments")
    if string_arguments and isinstance(arguments, str):
        try:
            # This JSON is the provider's native function.arguments, NOT message.content.
            arguments = json.loads(arguments, parse_constant=_reject_constant)
        except (ValueError, TypeError):
            arguments = None
    if not isinstance(arguments, dict):
        return AgentDecision(kind="protocol_error", error_code="invalid_arguments",
                             message="Native arguments must be a JSON object", raw_response=public)
    call_id = call.get("id")
    function_index = function.get("index")
    if function_index is not None and (type(function_index) is not int or function_index < 0):
        return AgentDecision(kind="protocol_error", error_code="invalid_function_index",
                             message="Native function index must be a nonnegative integer", raw_response=public)
    if require_call_id and (not isinstance(call_id, str) or not call_id):
        return AgentDecision(kind="protocol_error", error_code="missing_call_id",
                             message="Native call requires an id", raw_response=public)
    name = function["name"]
    summary = str(message.get("content") or f"Selected tool {name}")[:500]
    # Only a short public summary is archived for a legal call, never reasoning fields.
    public["content"] = summary
    return AgentDecision(summary, ToolCall(name, arguments, call_id, function_index), public)


def _reject_constant(value):
    raise ValueError(f"Non-JSON number: {value}")


def provider_tools(specs):
    return [{"type": "function", "function": {
        "name": spec.name, "description": spec.description, "parameters": spec.parameters,
    }} for spec in specs]
