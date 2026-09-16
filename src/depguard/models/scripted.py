"""Explicit test provider. Simulates model decisions, but does not fake tool evidence."""
from __future__ import annotations

import json
from pathlib import Path

from depguard.agent.contracts import AgentDecision, ToolCall, code_hash


class ScriptedTestModel:
    provider = "scripted_test"
    model_name = "scripted-test-model"
    one_shot_supported = False

    def __init__(self, actions, *, probe_actions=None):
        self.actions = actions
        self.probe_actions = probe_actions
        self.index = 0
        self.probe_index = 0

    @classmethod
    def from_file(cls, path):
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(value["actions"], probe_actions=value.get("probe_actions"))

    def probe_identity(self):
        return {"provider": self.provider, "model": self.model_name,
                "script": code_hash(repr((self.actions, self.probe_actions)))}

    def decide(self, messages, tools, *, timeout_seconds):
        probe = any(spec.name == "probe_echo" for spec in tools)
        observations = [message for message in messages if message["role"] == "tool"]
        latest = json.loads(observations[-1]["content"]) if observations else {}
        if probe and self.probe_actions is None:
            if not observations:
                call = ToolCall("probe_echo", {"token": "start"})
            elif "challenge" in latest:
                call = ToolCall("probe_echo", {"token": latest["challenge"]})
            else:
                call = ToolCall("finish", {"success": True})
            return AgentDecision("Follow the probe observation", call)
        actions = self.probe_actions if probe else self.actions
        index = self.probe_index if probe else self.index
        if index >= len(actions):
            return AgentDecision(kind="provider_error", error_code="script_exhausted",
                                 message="Script has no next response")
        event = actions[index]
        if probe:
            self.probe_index += 1
        else:
            self.index += 1
        if isinstance(event, AgentDecision):
            return event
        expect = event.get("expect", {})
        if expect and not observations:
            return AgentDecision(kind="provider_error", error_code="observation_mismatch",
                                 message="Required observation is missing")
        matched = all([
            "tool" not in expect or observations[-1].get("tool_name") == expect["tool"],
            "status" not in expect or latest.get("status") == expect["status"],
            "passed" not in expect or latest.get("evidence", {}).get("passed") == expect["passed"],
            "contains" not in expect or expect["contains"] in json.dumps(latest),
        ])
        if not matched:
            return AgentDecision(kind="provider_error", error_code="observation_mismatch",
                                 message="Required observation was not present in model context")
        kind = event.get("kind", "tool_call")
        if kind == "multiple_calls":
            return AgentDecision(kind="protocol_error", error_code="multiple_calls",
                                 message="Exactly one native call is required", raw_response=event)
        if kind != "tool_call":
            return AgentDecision(kind=kind, message=event.get("message", "Scripted response"),
                                 error_code=event.get("error_code"), raw_response=event)
        arguments = event.get("arguments", {})
        if probe and arguments == {"token": "$challenge"}:
            arguments = {"token": latest.get("challenge")}
        return AgentDecision(event.get("decision_summary", "Choose action from latest observation"),
                             ToolCall(event["name"], arguments), event)
