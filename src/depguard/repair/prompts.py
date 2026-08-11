from __future__ import annotations

import re

from depguard.schemas import RepairContext


def build_repair_prompt(context: RepairContext) -> str:
    package_issues = [
        f"{result.package}: {result.status}; {result.reason or 'no detail'}"
        for result in context.package_results
        if not result.exists
    ]
    api_issues = [
        (
            f"{result.reference.canonical_path}: {result.status}; "
            f"{result.reason or 'no detail'}"
        )
        for result in context.api_results
        if not result.api_valid
    ]
    suspicious = (
        context.suspicious_reference.canonical_path if context.suspicious_reference else "none"
    )
    candidates = ", ".join(context.candidate_apis) or "none"
    execution = context.execution_result
    runtime = (
        f"{execution.error_type or execution.error_category}: "
        f"{_compact_diagnostic(execution.stderr or execution.stdout)}"
        if execution and execution.status != "passed"
        else "none"
    )
    return (
        "Repair the Python program. Preserve its requirement and return the complete corrected "
        "program only, without Markdown or explanation.\n\n"
        f"Requirement: {context.requirement.strip() or '(not provided)'}\n\n"
        f"Program:\n{context.original_code.strip()}\n\n"
        f"Package findings: {' | '.join(package_issues) or 'none'}\n"
        f"API findings: {' | '.join(api_issues) or 'none'}\n"
        f"Suspicious API: {suspicious}\n"
        f"Candidate APIs: {candidates}\n"
        f"Runtime evidence: {runtime}\n"
    )


def _compact_diagnostic(text: str) -> str:
    if not text:
        return "none"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    relevant = [
        line.removeprefix("E   ")
        for line in lines
        if line.startswith("E   ")
        or re.search(r"(?:Error|Exception):", line)
        or "solution.py:" in line
    ]
    compact = " | ".join(relevant[-4:]) if relevant else " | ".join(lines[-3:])
    return compact[-600:]


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.search(r"```(?:python)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    stripped = re.sub(r"^```(?:python)?\s*", "", stripped, flags=re.IGNORECASE)
    return stripped.removesuffix("```").strip()
