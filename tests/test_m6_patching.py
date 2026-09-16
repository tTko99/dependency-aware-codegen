import time
from pathlib import Path

import pytest

from depguard.agent.patching import apply_patch, normalized_diff, rollback
from depguard.agent.safety import load_state


def state_at(tmp_path, code=b"x = 1\ny = 3\n"):
    source = tmp_path / "input.py"
    source.write_bytes(code)
    return load_state(source, project_root=tmp_path)


def patch(state, raw, **args):
    return apply_patch(state, {"patch": raw, "path": "input.py", **args}, time.monotonic()+5)


@pytest.mark.parametrize("header", ["@@ -999,2 +888,2 @@", "@@ -1,99 +1,81 @@", "@@"])
def test_body_authoritative_and_normalized(tmp_path, header):
    state = state_at(tmp_path)
    state.passed_checks["execute"] = state.version
    result = patch(state, header + "\n-x = 1\n+x = 2\n y = 3\n")
    assert result.status == "success"
    assert "@@ -1,2 +1,2 @@" in result.evidence["normalized_patch"]
    assert state.applied_patches == [result.evidence["normalized_patch"]]
    assert state.candidate_revision == 1 and state.version.startswith("1:")
    assert not state.passed_checks and state.candidate_history[0]["code"] == state.original_code
    assert state.source_path.read_bytes() == b"x = 1\ny = 3\n"


def test_headerless_requires_explicit_unique_target(tmp_path):
    state = state_at(tmp_path)
    raw = "@@\n-x = 1\n+x = 2"
    assert apply_patch(state, {"patch": raw}, 0).evidence["error_code"] == "PATCH_TARGET_REQUIRED"
    assert patch(state, raw).status == "success"


@pytest.mark.parametrize("raw,code", [
    ("", "PATCH_PARSE_ERROR"),
    ("@@ nope\n-x = 1\n+x = 2", "PATCH_PARSE_ERROR"),
    ("@@\n-z = 1\n+z = 2", "PATCH_CONTEXT_MISSING"),
    ("@@\n-x = 1\n+x = 2\n@@\n-z = 1\n+z = 2", "PATCH_CONTEXT_MISSING"),
    ("@@\n-x = 1\n+def broken(:", "PATCH_SYNTAX_ERROR"),
])
def test_atomic_errors_keep_version_and_give_rewrite_evidence(tmp_path, raw, code):
    state = state_at(tmp_path)
    version = state.version
    result = patch(state, raw)
    assert result.status == "error" and result.evidence["error_code"] == code
    assert result.evidence["error_line"] >= 1 and result.evidence["format_example"]
    assert result.evidence["raw_patch"] == raw
    assert state.version == version and state.candidate_code == state.original_code
    assert not state.candidate_history
    if code == "PATCH_SYNTAX_ERROR":
        assert result.evidence["column"] and result.evidence["context"]


def test_multiple_matches_not_disambiguated_by_model_line_number(tmp_path):
    state = state_at(tmp_path, b"x = 1\nx = 1\n")
    result = patch(state, "@@ -1 +1 @@\n-x = 1\n+x = 2")
    assert result.evidence["error_code"] == "PATCH_CONTEXT_AMBIGUOUS"


@pytest.mark.parametrize("source", [b"x = 1\ny = 3\n", b"x = 1\r\ny = 3\r\n",
                                     b"x = 1\ny = 3"])
def test_newline_convention_and_roundtrip(tmp_path, source):
    state = state_at(tmp_path, source)
    result = patch(state, "@@ -55,80 +55,99 @@\r\n-x = 1\r\n+x = 2\r\n")
    expected = source.replace(b"x = 1", b"x = 2")
    assert result.status == "success" and state.candidate_code.encode() == expected
    other = state_at(tmp_path, source)
    replay = apply_patch(other, {"patch": result.evidence["normalized_patch"]}, 0)
    assert replay.status == "success" and other.candidate_code.encode() == expected


def test_explicit_missing_newline_marker(tmp_path):
    state = state_at(tmp_path, b"x = 1\n")
    result = patch(state, "@@\n-x = 1\n+x = 2\n\\ No newline at end of file\n")
    assert result.status == "success" and state.candidate_code == "x = 2"
    assert "\\ No newline at end of file" in normalized_diff("x = 1\n", "x = 2", "input.py")


def test_normalized_diff_can_add_final_newline(tmp_path):
    state = state_at(tmp_path, b"x = 1")
    raw = normalized_diff("x = 1", "x = 2\n", "input.py")
    assert patch(state, raw).status == "success"
    assert state.candidate_code == "x = 2\n"


def test_resolved_escape_branch_without_symlink_privilege(tmp_path, monkeypatch):
    state = state_at(tmp_path)
    resolve = Path.resolve
    def redirected(self, *args, **kwargs):
        if self.name == "link.py":
            return tmp_path.parent / "outside.py"
        return resolve(self, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", redirected)
    result = patch(state, "--- a/link.py\n+++ b/link.py\n@@\n-x = 1\n+x = 2")
    assert result.evidence["error_code"] == "SYMLINK_ESCAPE"


@pytest.mark.parametrize("path,code", [
    ("../input.py", "PATH_OUTSIDE_ROOT"), ("C:/outside.py", "PATH_OUTSIDE_ROOT"),
    ("/outside.py", "PATH_OUTSIDE_ROOT"), ("test_input.py", "TEST_FILE_READ_ONLY"),
    ("tests/input.py", "TEST_FILE_READ_ONLY"), ("other.py", "PATH_NOT_IN_WRITE_SCOPE"),
    (".git/config", "PATH_NOT_IN_WRITE_SCOPE"), (".venv/code.py", "PATH_NOT_IN_WRITE_SCOPE"),
    (".env", "PATH_NOT_IN_WRITE_SCOPE"), ("build/input.py", "PATH_NOT_IN_WRITE_SCOPE"),
])
def test_tool_internal_path_refusal(tmp_path, path, code):
    state = state_at(tmp_path)
    result = patch(state, f"--- a/{path}\n+++ b/{path}\n@@\n-x = 1\n+x = 2")
    assert result.status == "denied" and result.evidence["error_code"] == code
    assert state.candidate_revision == 0


def test_symlink_escape(tmp_path):
    state = state_at(tmp_path)
    outside = tmp_path.parent / (tmp_path.name + "-outside.py")
    outside.write_text("x = 1\n")
    try:
        try:
            (tmp_path / "link.py").symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"Host does not permit symlink creation: {exc}")
        result = patch(state, "--- a/link.py\n+++ b/link.py\n@@\n-x = 1\n+x = 2")
        assert result.evidence["error_code"] == "SYMLINK_ESCAPE"
    finally:
        outside.unlink()


def test_binary_and_explicit_scope(tmp_path):
    state = state_at(tmp_path, b"x = 1\x00\n")
    assert patch(state, "@@\n-x = 1\n+x = 2").evidence["error_code"] == "BINARY_FILE_UNSUPPORTED"
    state = state_at(tmp_path)
    state.write_scope.clear()
    assert patch(state, "@@\n-x = 1\n+x = 2").evidence["error_code"] == "PATH_NOT_IN_WRITE_SCOPE"


def test_global_rollback_revision_and_history(tmp_path):
    state = state_at(tmp_path)
    assert patch(state, "@@\n-x = 1\n+x = 2").status == "success"
    assert patch(state, "@@\n-y = 3\n+y = 4").status == "success"
    rollback(state, {}, 0)
    assert state.candidate_revision == 3 and len(state.candidate_history) == 3
    assert state.candidate_code == state.original_code
    assert state.source_path.read_bytes() == state.original_code.encode()
    assert not state.applied_patches and not list(tmp_path.glob(".depguard-*"))


def test_large_invalid_patch_has_bounded_rewrite_evidence(tmp_path):
    state = state_at(tmp_path)
    raw = "not a patch\n" + "x" * 10000
    result = patch(state, raw)
    assert result.status == "error" and len(result.evidence["raw_patch"]) <= 4000
    assert "TRUNCATED" in result.evidence["raw_patch"] and result.evidence["format_example"]
    assert state.candidate_revision == 0


def test_successful_multiple_hunks_preserve_order(tmp_path):
    state = state_at(tmp_path)
    result = patch(state, "@@ -99,8 +88,4 @@\n-x = 1\n+x = 2\n@@ -2,7 +2,9 @@\n-y = 3\n+y = 4")
    assert result.status == "success" and state.candidate_code == "x = 2\ny = 4\n"
