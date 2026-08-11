from __future__ import annotations

import re

from depguard.schemas import ErrorCategory

_TRACEBACK_TYPE_RE = re.compile(
    r"^(?:E\s+)?([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):", re.MULTILINE
)


def extract_error_type(stderr: str) -> str | None:
    matches = _TRACEBACK_TYPE_RE.findall(stderr or "")
    return matches[-1] if matches else None


def classify_execution_error(
    stderr: str,
    *,
    return_code: int | None = None,
    timed_out: bool = False,
) -> ErrorCategory:
    if timed_out:
        return ErrorCategory.TIMEOUT
    if return_code == 0:
        return ErrorCategory.UNKNOWN

    text = stderr or ""
    error_type = extract_error_type(text)

    if error_type in {"SyntaxError", "IndentationError", "TabError"}:
        return ErrorCategory.SYNTAX_ERROR
    if error_type in {"ImportError", "ModuleNotFoundError"}:
        return ErrorCategory.IMPORT_ERROR
    if error_type == "NameError":
        return ErrorCategory.NAME_ERROR
    if error_type == "AttributeError":
        return ErrorCategory.ATTRIBUTE_ERROR
    if error_type == "ValueError":
        return ErrorCategory.VALUE_ERROR
    if error_type == "TypeError":
        lowered = text.lower()
        argument_markers = (
            "argument",
            "positional",
            "keyword",
            "required",
            "missing",
            "takes",
            "got an unexpected",
        )
        if any(marker in lowered for marker in argument_markers):
            return ErrorCategory.INCORRECT_ARGUMENTS
        return ErrorCategory.TYPE_ERROR
    if error_type:
        return ErrorCategory.RUNTIME_ERROR
    return ErrorCategory.UNKNOWN
