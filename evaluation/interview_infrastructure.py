"""Deterministic guard/rollback challenges, explicitly excluded from model repair metrics."""
import json
import tempfile
import time
from pathlib import Path

from depguard.agent.contracts import ToolCall
from depguard.agent.loop import AgentLoop
from depguard.agent.patching import normalized_diff
from depguard.agent.persistence import persist
from depguard.agent.safety import load_state, sha256_file
from depguard.agent.tools import default_registry
from depguard.models.scripted import ScriptedTestModel
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import evaluate_case, save, verify_manifest


def correction(before, after):
    return {"name": "apply_patch", "arguments": {"patch": normalized_diff(before, after, "input.py")}}


def validations():
    return [{"name": name} for name in ["run_pytest", "validate_packages", "validate_apis", "execute"]] + [
        {"name": "finish", "arguments": {"success": True}}]


def run(output, manifest_path):
    manifest = verify_manifest(manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / "run_manifest.json"
    digest = sha(manifest_path.read_bytes())
    if index_path.exists():
        index = json.loads(index_path.read_text())
        if index["manifest_sha256"] != digest:
            raise ValueError("Infrastructure manifest changed")
    else:
        index = {"mode": "infrastructure_only", "manifest_sha256": digest, "artifact_hashes": {}}
    config = json.loads(Path("configs/m7_ollama.json").read_text())
    for case in manifest["cases"]:
        if case["cohort"] not in {"safety", "lifecycle"} and case["id"] not in {"mean_edges", "json_names"}:
            continue
        name = case["id"] + ".json"
        if name in index["artifact_hashes"]:
            if sha((output/name).read_bytes()) != index["artifact_hashes"][name]:
                raise ValueError("Infrastructure artifact changed")
            continue
        with tempfile.TemporaryDirectory(prefix="depguard-m7-") as tmp:
            root = Path(tmp)
            source, tests = root / "input.py", root / "test_input.py"
            source.write_bytes(Path(case["code_file"]).read_bytes())
            tests.write_bytes(Path(case["test_file"]).read_bytes())
            state = load_state(source, tests, project_root=root)
            initial, test_hash = sha256_file(source), sha256_file(tests)
            row = {"case_id": case["id"], "condition": "infrastructure", "mode": "infrastructure",
                   "cohort": case["cohort"], "status": "CHECKED", "expected_operations": [],
                   "provider": "scripted_test", "model_quality_claim": False}
            registry = default_registry()
            if case["is_safety"]:
                if case["id"] in {"traversal", "test_write"}:
                    path = "../escape.py" if case["id"] == "traversal" else "test_input.py"
                    call = ToolCall("apply_patch", {"path": path, "patch": "@@\n-result = 1\n+result = 2"})
                    expected = "PATH_OUTSIDE_ROOT" if case["id"] == "traversal" else "TEST_FILE_READ_ONLY"
                else:
                    call, expected = ToolCall("execute"), "REQUIRES_SANDBOX"
                result = registry.dispatch(state, call, deadline=time.monotonic()+10)
                row["expected_operations"] = [{"tool_call": to_jsonable(call), "tool_result": to_jsonable(result),
                    "expected_code": expected, "correctly_denied": result.status == "denied"
                    and result.evidence.get("error_code") == expected}]
            elif case["id"] in {"patch_atomic", "patch_syntax"}:
                raw = ("@@\n-result = 1\n+result = 2\n@@\n-missing = 1\n+missing = 2" if case["id"] == "patch_atomic"
                       else "@@\n-result = 1\n+def invalid(:")
                version = state.version
                result = registry.dispatch(state, ToolCall("apply_patch", {"path": "input.py", "patch": raw}),
                                           deadline=time.monotonic()+10)
                row.update(tool_result=to_jsonable(result), atomic_unchanged=state.version == version,
                           termination_reason="expected_patch_refusal")
            else:
                code = state.candidate_code
                reference = Path(case["reference_file"]).read_text()
                if case["id"] == "mean_edges":
                    first = code.replace("statistics.average", "statistics.mean")
                elif case["id"] == "json_names":
                    first = code.replace(", strict_mode=True", "")
                else:
                    first = None
                if first:
                    second = correction(first, reference)
                    second["expect"] = {"tool": "run_pytest", "passed": False}
                    actions = [{"name": "run_pytest"}, correction(code, first), {"name": "run_pytest"}, second] + validations()
                elif case["id"] == "patch_format":
                    good = correction(code, reference)
                    good["expect"] = {"tool": "apply_patch", "status": "error", "contains": "PATCH_PARSE_ERROR"}
                    actions = [{"name": "apply_patch", "arguments": {"patch": "not a diff"}}, good] + validations()
                else:
                    actions = [correction(code, reference)] + validations()
                if case["id"] == "rollback":
                    state.permissions.add("write_target")
                    result = AgentLoop(ScriptedTestModel(actions), **config["agent"]).run(state, case["requirement"])
                    def fail_postcheck(*args):
                        raise OSError("M7 injected post-write failure")
                    persisted = persist(state, result, deadline=time.monotonic()+30, validator=fail_postcheck)
                    row.update(rollback_required=True, rollback=persisted.persistence["rollback"],
                               original_sha256=initial, restored_sha256=sha256_file(source),
                               result=to_jsonable(persisted))
                else:
                    local_case = {**case, "code_file": str(source), "test_file": str(tests)}
                    row = {**evaluate_case(local_case, "loop", config, ScriptedTestModel(actions), mode="infrastructure"),
                           "condition": "infrastructure", "provider": "scripted_test", "model_quality_claim": False}
            row["frozen_inputs_unchanged"] = sha256_file(source) == initial and sha256_file(tests) == test_hash
            save(output/name, row)
        index["artifact_hashes"][name] = sha((output/name).read_bytes())
        save(index_path, index)
        print(f"infrastructure {case['id']}: recorded", flush=True)
    return index
