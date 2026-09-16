"""Host-only commit after finish, with snapshot, conflict detection and rollback."""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from depguard.agent.contracts import ToolCall
from depguard.agent.deadline import bounded
from depguard.agent.paths import path_guard
from depguard.agent.regression import verification
from depguard.agent.safety import integrity_guard, load_state, sha256_file
from depguard.agent.tools import default_registry, dispatch_worker
from depguard.schemas import to_jsonable


class PostValidationError(OSError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def _atomic_write(path, data):
    descriptor, name = tempfile.mkstemp(prefix=".depguard-write-", dir=path.parent)
    staging = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def post_validate(state, deadline):
    checked = load_state(state.source_path, state.test_path, project_root=state.project_root,
                         permissions=state.permissions, risk_policy=state.risk_policy,
                         execution_timeout_seconds=state.execution_timeout_seconds,
                         config_paths=state.config_hashes)
    if checked.candidate_code != state.candidate_code:
        raise OSError("Written source differs from candidate")
    registry = default_registry()
    evidence = {}
    names = ["validate_packages", "validate_apis", "execute"]
    if state.test_path:
        names.append("run_pytest")
    for name in names:
        result, checked = bounded(dispatch_worker,
                                  (registry, checked, ToolCall(name), deadline), deadline)
        evidence[name] = to_jsonable(result)
        if result.status != "success" or result.evidence.get("passed") is not True:
            raise PostValidationError(f"Post-write validation failed: {name}: {result.message}",
                                      evidence)
    return evidence


def persist(state, result, *, deadline, validator=post_validate):
    started = time.monotonic()
    details = {"rollback": {"attempted": False, "succeeded": False,
                            "failure_reason": None, "restored_sha256": None}}
    if result.final_status != "PASS" or result.termination_reason != "finish":
        return replace(result, persistence={**details, "written": False,
                                            "reason": "requires verified PASS"})
    snapshot = None
    wrote = False
    candidate_bytes = state.candidate_code.encode("utf-8")
    candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()
    original = None
    write_attempted = False
    try:
        if not {"read_source", "write_target", "write_temp"} <= state.permissions:
            raise PermissionError("Commit requires read_source, write_target and write_temp")
        if time.monotonic() >= deadline:
            raise TimeoutError("Deadline expired before commit")
        refusal = integrity_guard(state)
        if refusal:
            details["refusal"] = to_jsonable(refusal)
            raise OSError(refusal.message)
        refusal = path_guard(state, state.source_path.relative_to(state.project_root).as_posix())
        if refusal:
            details["refusal"] = to_jsonable(refusal)
            raise PermissionError(refusal.message)
        checks = verification(state)
        details["pre_write_verification"] = checks
        finished = any(step.tool_call and step.tool_call.name == "finish"
                       and step.tool_result.status == "success" for step in result.trajectory[-1:])
        if (not finished or result.candidate_version != state.version
                or result.candidate_code != state.candidate_code or checks["host_status"] != "PASS"):
            raise OSError("Current candidate lacks verified finish and complete current evidence")
        original = state.source_path.read_bytes()
        if hashlib.sha256(original).hexdigest() != state.input_hashes[str(state.source_path)]:
            raise OSError("Source conflict before snapshot")
        fd, name = tempfile.mkstemp(prefix=".depguard-original-", suffix=".bak",
                                    dir=state.source_path.parent)
        snapshot = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        state.snapshots[str(snapshot)] = original
        details["snapshot"] = str(snapshot)
        refusal = integrity_guard(state)
        if refusal:
            details["refusal"] = to_jsonable(refusal)
            raise OSError("Input conflict before write")
        write_attempted = True
        _atomic_write(state.source_path, candidate_bytes)
        wrote = True
        if sha256_file(state.source_path) != candidate_hash:
            raise OSError("Post-write source hash differs from candidate")
        if state.test_path and sha256_file(state.test_path) != state.input_hashes[str(state.test_path)]:
            raise OSError("Tests changed after write")
        details["post_write_checks"] = validator(state, deadline)
        for name in state.required_checks:
            check = details["post_write_checks"].get(name, {})
            if check.get("status") != "success" or check.get("evidence", {}).get("passed") is not True:
                raise OSError(f"Missing or failed post-write evidence: {name}")
        if time.monotonic() >= deadline:
            raise TimeoutError("Deadline expired during commit")
        if sha256_file(state.source_path) != candidate_hash:
            raise OSError("Source changed during post-write validation")
        if state.test_path and sha256_file(state.test_path) != state.input_hashes[str(state.test_path)]:
            raise OSError("Tests changed during validation")
        for name, expected in state.config_hashes.items():
            if sha256_file(Path(name)) != expected:
                raise OSError("Configuration changed during validation")
        snapshot.unlink()
        state.snapshots.clear()
        details.update(written=True, snapshot_cleaned=True)
        return replace(result, applied=True, persistence=details,
                       elapsed_seconds=result.elapsed_seconds + time.monotonic() - started)
    except BaseException as exc:  # noqa: BLE001 - also restore after interruption during write
        if isinstance(exc, PostValidationError):
            details["post_write_checks"] = exc.evidence
        details.update(error=f"{type(exc).__name__}: {exc}", written=wrote)
        rollback_result = "not_written"
        reason = "write_failed"
        if write_attempted:
            details["rollback"]["attempted"] = True
            try:
                actual = sha256_file(state.source_path)
                original_hash = state.input_hashes[str(state.source_path)]
                if actual not in {candidate_hash, original_hash}:
                    raise OSError("External write conflict; preserving external content and snapshot")
                if actual != original_hash:
                    _atomic_write(state.source_path, original)
                if sha256_file(state.source_path) != original_hash:
                    raise OSError("Restored source hash mismatch")
                rollback_result = "restored_initial" if wrote or actual != original_hash else "not_written"
                details["rollback"].update(succeeded=True, restored_sha256=original_hash)
            except BaseException as rollback_error:  # noqa: BLE001 - retain recovery evidence
                rollback_result = "failed"
                reason = "rollback_failed"
                details["rollback_error"] = str(rollback_error)
                details["rollback"]["failure_reason"] = str(rollback_error)
        if snapshot and snapshot.exists():
            details["recovery_path"] = str(snapshot)
        state.rollback_result = rollback_result
        return replace(result, final_status="ERROR", termination_reason=reason,
                       rollback_result=rollback_result, persistence=details,
                       elapsed_seconds=result.elapsed_seconds + time.monotonic() - started)
