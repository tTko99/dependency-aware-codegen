"""Host-only bounded observations; full results live in the trajectory artifact."""
from __future__ import annotations

import json

from depguard.schemas import to_jsonable


def clip_text(text, limit):
    if len(text) <= limit:
        return text
    marker = "\n[TRUNCATED; see raw trajectory]\n"
    available = max(0, limit - len(marker))
    head = available // 3
    return text[:head] + marker + (text[-(available-head):] if available > head else "")


def compact_observation(result, limit):
    raw = to_jsonable(result)
    if len(json.dumps(raw)) <= limit:
        return raw
    evidence = raw.get("evidence", {})
    # Failed tests, exception type and locations take precedence over bulk output.
    selected = {key: value for key, value in evidence.items() if key in {
        "passed", "kind", "error_line", "syntax_error", "failed_test", "error_type",
        "missing_checks", "false_success", "preview", "raw_patch", "retry_allowed",
        "error_code", "format_example", "column", "context", "regression_guard", "rollback",
        "failed_checks", "stale_checks", "allowed_next_tools", "validation_state",
    }}
    execution = evidence.get("execution", {})
    if execution:
        selected["execution"] = {key: execution[key] for key in (
            "status", "return_code", "error_type", "error_category", "timed_out",
            "stdout", "stderr",
        ) if key in execution}
    compact = {"status": raw["status"], "message": raw["message"], "evidence": selected,
               "candidate_version": raw["candidate_version"], "cached": raw["cached"],
               "truncated": True}

    def shorten(value, size):
        if isinstance(value, str):
            return clip_text(value, size)
        if isinstance(value, dict):
            return {k: shorten(v, size) for k, v in value.items()}
        return value

    for size in (limit // 4, limit // 8, 80):
        candidate = shorten(compact, size)
        if len(json.dumps(candidate)) <= limit:
            return candidate
    # Very small budgets still have a hard serialized character cap.
    fallback = {"status": raw["status"], "truncated": True, "excerpt": ""}
    text = json.dumps(selected or evidence)
    room = max(0, limit - len(json.dumps(fallback)))
    fallback["excerpt"] = clip_text(text, room)
    while len(json.dumps(fallback)) > limit and fallback["excerpt"]:
        fallback["excerpt"] = fallback["excerpt"][:-1]
    return fallback


def action_messages(call, summary, observation, step):
    call_id = call.call_id or f"host_call_{step}"
    function = {"name": call.name, "arguments": call.arguments}
    if call.function_index is not None:
        function["index"] = call.function_index
    return [
        {"role": "assistant", "content": summary, "tool_calls": [{
            "id": call_id, "type": "function",
            "function": function,
        }]},
        {"role": "tool", "tool_name": call.name, "tool_call_id": call_id,
         "content": json.dumps(observation)},
    ]
