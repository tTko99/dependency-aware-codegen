from __future__ import annotations

import ast
import difflib
import re

from depguard.agent.context import clip_text
from depguard.agent.contracts import ToolResult, code_hash
from depguard.agent.paths import path_guard
from depguard.agent.safety import integrity_guard

FORMAT_EXAMPLE = "--- a/path.py\n+++ b/path.py\n@@ -1 +1 @@\n-result = 1\n+result = 2\n"


class PatchError(ValueError):
    def __init__(self, message, line, code="PATCH_PARSE_ERROR", **details):
        super().__init__(message)
        self.line, self.code, self.details = line, code, details


def normalized_diff(before, after, path):
    rows = difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                               fromfile="a/" + path, tofile="b/" + path)
    return "".join(row if row.endswith("\n") else row + "\n\\ No newline at end of file\n"
                   for row in rows)


def _header_path(raw):
    raw = raw.split("\t", 1)[0]
    return raw[2:] if raw.startswith(("a/", "b/")) else raw


def parse_apply(raw, state, *, path=None):
    lines = raw.splitlines()
    if lines and lines[0].startswith("```") and lines[-1] == "```":
        lines = lines[1:-1]
    index = 0
    if lines and lines[0].startswith("--- "):
        if len(lines) < 2 or not lines[1].startswith("+++ "):
            raise PatchError("Expected +++ target header", 2)
        index = 2
    elif not lines or not lines[0].startswith("@@"):
        raise PatchError("Expected ---/+++ headers or @@ hunk", 1)
    elif path is None:
        raise PatchError("Headerless patch requires explicit path for the unique target", 1,
                         "PATCH_TARGET_REQUIRED")
    original = state.candidate_code.splitlines()
    changes = []
    last_end = 0
    eof_newline = state.candidate_code.endswith("\n")
    newline = "\r\n" if "\r\n" in state.candidate_code else "\n"
    while index < len(lines):
        header_line = index + 1
        if lines[index] != "@@" and not re.fullmatch(
                r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@.*", lines[index]):
            raise PatchError("Malformed hunk header", header_line)
        index += 1
        before, after = [], []
        edited = False
        no_newline_after = False
        no_newline_before = False
        previous_prefix = None
        while index < len(lines) and not lines[index].startswith("@@"):
            line = lines[index]
            if line == "\\ No newline at end of file":
                if previous_prefix is None:
                    raise PatchError("Misplaced newline marker", index + 1)
                if previous_prefix in "+ ":
                    no_newline_after = True
                if previous_prefix in "- ":
                    no_newline_before = True
                previous_prefix = None
                index += 1
                continue
            if not line or line[0] not in " +-" or line.startswith(("--- ", "+++ ")):
                raise PatchError("Invalid hunk line or multiple target files", index + 1)
            if line[0] in " -":
                before.append(line[1:])
            if line[0] in " +":
                if no_newline_after:
                    raise PatchError("Newline marker before last output line", index + 1)
                after.append(line[1:])
            previous_prefix = line[0]
            edited |= line[0] in "+-"
            index += 1
        if not edited:
            raise PatchError("Hunk has no edits", header_line)
        # Ignore header coordinates/counts; exact body matching determines the target.
        positions = [i for i in range(last_end, len(original) - len(before) + 1)
                     if original[i:i + len(before)] == before]
        if len(positions) != 1:
            code = "PATCH_CONTEXT_MISSING" if not positions else "PATCH_CONTEXT_AMBIGUOUS"
            raise PatchError("Hunk context is missing or ambiguous; add unique context", header_line,
                             code, matches=len(positions))
        start, end = positions[0], positions[0] + len(before)
        if changes and start == changes[-1][0]:
            raise PatchError("Overlapping hunks", header_line)
        if no_newline_after and end != len(original):
            raise PatchError("Newline marker is not at file end", header_line)
        if end == len(original):
            if no_newline_after:
                eof_newline = False
            elif no_newline_before:
                eof_newline = True
        changes.append((start, end, after))
        last_end = end
    if not changes:
        raise PatchError("Patch contains no hunks", index + 1)
    candidate = list(original)
    for start, end, after in reversed(changes):
        candidate[start:end] = after
    code = newline.join(candidate) + (newline if candidate and eof_newline else "")
    try:
        ast.parse(code)
    except (SyntaxError, ValueError) as exc:
        raise PatchError("Candidate syntax error; regenerate patch", getattr(exc, "lineno", 1) or 1,
                         "PATCH_SYNTAX_ERROR", column=getattr(exc, "offset", None),
                         context=clip_text(getattr(exc, "text", "") or str(exc), 240)) from exc
    return code


def apply_patch(state, args, deadline):
    raw = args["patch"]
    if "read_source" not in state.permissions:
        return ToolResult("denied", "Permission denied", {"missing_permissions": ["read_source"]},
                          state.version)
    refusal = integrity_guard(state)
    if refusal:
        return refusal
    target = state.source_path.relative_to(state.project_root).as_posix()
    paths = [args["path"]] if "path" in args else []
    paths += [_header_path(line[4:]) for line in raw.splitlines()
              if line.startswith(("--- ", "+++ "))]
    for path in paths or [target]:
        refusal = path_guard(state, path)
        if refusal:
            return refusal
    try:
        candidate = parse_apply(raw, state, path=args.get("path"))
        if candidate == state.candidate_code:
            raise PatchError("Patch makes no change", 1, "PATCH_NO_CHANGE")
    except PatchError as exc:
        return ToolResult("error", str(exc), {"raw_patch": clip_text(raw, 4000),
                          "error_line": exc.line, "error_code": exc.code,
                          "format_example": FORMAT_EXAMPLE, **exc.details}, state.version)
    preview = normalized_diff(state.candidate_code, candidate, target)
    before = {"version": state.version, "sha256": code_hash(state.candidate_code),
              "lines": len(state.candidate_code.splitlines())}
    state.candidate_history.append({"version": state.version, "code": state.candidate_code,
                                    "patch": preview})
    state.candidate_code = candidate
    state.candidate_revision += 1
    state.applied_patches.append(preview)
    state.passed_checks.clear()
    state.check_state_versions.clear()
    state.cache.clear()
    from depguard.agent.regression import regression_guard

    return ToolResult("success", "Memory candidate updated (dry-run; target file unchanged)",
                      {"preview": preview, "normalized_patch": preview, "written": False,
                       "before": before, "after": {"version": state.version,
                       "sha256": code_hash(candidate), "lines": len(candidate.splitlines())},
                       "regression_guard": regression_guard(state)}, state.version)


def rollback(state, args, deadline):
    state.candidate_history.append({"version": state.version, "code": state.candidate_code,
                                    "operation": "rollback"})
    state.candidate_code = state.original_code
    state.candidate_revision += 1
    state.applied_patches.clear()
    state.passed_checks.clear()
    state.check_state_versions.clear()
    state.cache.clear()
    state.rollback_result = "memory_restored"
    return ToolResult("success", "Restored initial memory candidate", {
        "rollback": {"attempted": True, "succeeded": True, "failure_reason": None,
                     "restored_sha256": code_hash(state.original_code)}}, state.version)
