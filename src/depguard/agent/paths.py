"""Single-file write scope, checked inside patch and persistence boundaries."""
from pathlib import Path, PurePosixPath

from depguard.agent.contracts import ToolResult

BLOCKED = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".ruff_cache",
           ".mypy_cache", ".cache", "node_modules", "build", "dist", "htmlcov",
           ".ssh", ".aws", ".azure", ".codex", ".agents"}


def path_guard(state, raw):
    def deny(code, message):
        return ToolResult("denied", message, {"error_code": code, "path": str(raw)}, state.version)

    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return deny("PATH_OUTSIDE_ROOT", "Invalid path")
    parts = PurePosixPath(raw.replace("\\", "/")).parts
    if ".." in parts or Path(raw).is_absolute() or ":" in raw or raw.startswith(("/", "\\")):
        return deny("PATH_OUTSIDE_ROOT", "Only project-relative paths without traversal are allowed")
    lexical = state.project_root / raw
    try:
        target = lexical.resolve()
    except (OSError, RuntimeError):
        return deny("SYMLINK_ESCAPE", "Cannot resolve target")
    if not target.is_relative_to(state.project_root):
        return deny("SYMLINK_ESCAPE", "Resolved target escapes project root")
    relative = target.relative_to(state.project_root)
    all_parts = {p.lower() for p in (*parts, *relative.parts)}
    if (target == state.test_path or all_parts & {"test", "tests", "testing"}
            or target.name.lower().startswith("test_") or target.name.lower().endswith("_test.py")
            or target.name.lower() == "conftest.py"):
        return deny("TEST_FILE_READ_ONLY", "Tests are read-only")
    if (all_parts & BLOCKED or any(p.startswith(".env") for p in all_parts)
            or target.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
            or target.name.lower() in {"credentials", "credentials.json", "secrets.json",
                "secrets.yaml", "secrets.yml", "secrets.py", ".netrc", ".npmrc", ".pypirc",
                "id_rsa", "id_ed25519"}):
        return deny("PATH_NOT_IN_WRITE_SCOPE", "Protected path")
    if str(target) not in state.write_scope or target != state.source_path:
        return deny("PATH_NOT_IN_WRITE_SCOPE", "Target is not the authorized source")
    try:
        data = target.read_bytes()
        data.decode("utf-8")
    except UnicodeError:
        return deny("BINARY_FILE_UNSUPPORTED", "Target is not UTF-8 text")
    except OSError:
        return deny("SOURCE_INTEGRITY_MISMATCH", "Target unavailable")
    if b"\x00" in data or target.suffix.lower() != ".py":
        return deny("BINARY_FILE_UNSUPPORTED", "Only text Python targets are supported")
    return None
