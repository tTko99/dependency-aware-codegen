"""Isolated, side-effect-free provider capability probe. Never dispatches real tools."""
from __future__ import annotations

import copy
import json
import secrets
import time
from dataclasses import dataclass, field, replace

from depguard.agent.context import action_messages
from depguard.agent.contracts import AgentDecision, ToolSpec, code_hash
from depguard.agent.deadline import bounded
from depguard.agent.tools import ProtocolError, ToolRegistry
from depguard.schemas import to_jsonable

SCHEMA_VERSION = "native-audited-v2"
_CACHE = {}


@dataclass(frozen=True)
class ProbeResult:
    status: str
    stage: str
    reason: str
    model_response_kind: str | None = None
    cached: bool = False
    elapsed_seconds: float = 0.0
    transcript: list[dict] = field(default_factory=list)
    termination_reason: str = ""


def clear_probe_cache():
    _CACHE.clear()


def probe_specs():
    return [ToolSpec("probe_echo", "Probe only: echo the requested token; has no side effects", {
        "type": "object", "properties": {"token": {"type": "string"}},
        "required": ["token"], "additionalProperties": False,
    }), ToolSpec("finish", "End this probe after echoing the observation challenge", {
        "type": "object", "properties": {"success": {"type": "boolean"},
                                           "conclusion": {"type": "string"}},
        "required": [], "additionalProperties": False,
    })]


def _probe_worker(model, timeout_seconds):
    # Only internal in-memory probe tools are exposed. No AgentState is accepted here.
    registry = ToolRegistry()
    for spec in probe_specs():
        registry.register(spec, None)
    messages = [{"role": "system", "content": (
        "Capability probe. Use exactly one native tool call per response, no JSON text. "
        "First call probe_echo with token=start. Read its observation and echo the challenge "
        "in a second probe_echo call. After its acknowledgment, call finish."
    )}]
    challenge = secrets.token_hex(12)
    deadline = time.monotonic() + timeout_seconds
    transcript = []
    for stage, expected_name, token in [("first_call", "probe_echo", "start"),
                                        ("observation_followup", "probe_echo", challenge),
                                        ("finish", "finish", None)]:
        decision = model.decide(messages, registry.specs,
                                timeout_seconds=max(.001, deadline-time.monotonic()))
        if not isinstance(decision, AgentDecision):
            return ProbeResult("failed", stage, "Untyped/text response", "text", transcript=transcript)
        transcript.append({"stage": stage, "kind": decision.kind,
                           "decision_summary": decision.decision_summary,
                           "tool_call": to_jsonable(decision.tool_call),
                           "error_code": decision.error_code})
        if isinstance(decision.raw_response, dict):
            transcript[-1]["usage"] = decision.raw_response.get("usage", {})
            transcript[-1]["response_model"] = decision.raw_response.get("provider_model")
            transcript[-1]["argument_type"] = decision.raw_response.get("argument_type")
        transcript[-1]["tool_call_id"] = decision.tool_call.call_id if decision.tool_call else None
        transcript[-1]["termination_reason"] = "continue"
        if decision.kind != "tool_call":
            return ProbeResult("failed", stage, decision.message or "Expected native tool call",
                               decision.kind, transcript=transcript)
        try:
            registry.validate(decision.tool_call)
        except ProtocolError as exc:
            return ProbeResult("failed", stage, str(exc), "protocol_error", transcript=transcript)
        call = decision.tool_call
        if call.name != expected_name or token is not None and call.arguments.get("token") != token:
            return ProbeResult("failed", stage, "Action did not follow the latest probe observation",
                               decision.kind, transcript=transcript)
        observation = ({"challenge": challenge, "next_action": "echo this challenge"}
                       if stage == "first_call" else {"acknowledged": True, "next_action": "finish"}
                       if stage != "finish" else {"finished": True, "arguments": call.arguments})
        transcript[-1]["observation"] = observation
        messages.extend(action_messages(call, decision.decision_summary, observation, stage))
    return ProbeResult("passed", "complete", "Native calls, observation followup and finish verified",
                       "tool_call", transcript=transcript)


def run_probe(model, specs, *, timeout_seconds=30, use_cache=True):
    started = time.monotonic()
    identity = model.probe_identity() if hasattr(model, "probe_identity") else None
    key = code_hash(json.dumps([identity, SCHEMA_VERSION, to_jsonable(specs)], sort_keys=True))
    if use_cache and identity is not None and key in _CACHE:
        return replace(_CACHE[key], cached=True, elapsed_seconds=time.monotonic()-started)
    try:
        isolated = copy.deepcopy(model)
        result = bounded(_probe_worker, (isolated, timeout_seconds), started + timeout_seconds)
    except TimeoutError:
        result = ProbeResult("failed", "deadline", "Capability probe timed out", "provider_error")
    except Exception:  # noqa: BLE001 - provider exception details may contain credentials
        result = ProbeResult("failed", "provider", "Capability probe provider failed", "provider_error")
    result = replace(result, elapsed_seconds=time.monotonic()-started)
    reason = "finish" if result.status == "passed" else "probe_rejected"
    if result.transcript:
        result.transcript[-1]["termination_reason"] = reason
    result = replace(result, termination_reason=reason)
    # Transient outages and protocol failures must not poison future sessions.
    if use_cache and identity is not None and result.status == "passed":
        _CACHE[key] = result
    return result
