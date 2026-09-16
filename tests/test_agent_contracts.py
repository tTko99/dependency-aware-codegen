import json
from pathlib import Path

from depguard.agent.contracts import AgentState, ToolCall, ToolResult, TrajectoryStep
from depguard.schemas import to_jsonable


def test_contracts_preserve_structured_evidence_and_raw_observation():
    result = ToolResult("denied", "input changed", {"expected": "a", "actual": "b"})
    step = TrajectoryStep(1, "Check current test outcome", ToolCall("run_pytest"), result, "utc")
    payload = json.loads(json.dumps(to_jsonable(step)))
    assert payload["tool_result"]["status"] == "denied"
    assert payload["tool_result"]["evidence"]["actual"] == "b"
    assert {"step", "thought", "tool_call", "tool_result", "timestamp"} <= payload.keys()


def test_state_version_tracks_candidate_and_instances_do_not_share_evidence():
    first = AgentState("x=1", "x=1", Path("."), Path("input.py"))
    second = AgentState("x=1", "x=1", Path("."), Path("input.py"))
    version = first.version
    first.candidate_code = "x=2"
    first.passed_checks["execute"] = version
    assert first.version != version
    assert not second.passed_checks
