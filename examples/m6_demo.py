"""Local deterministic M6 evidence. Uses real validation, no model service or Git."""
import json
import tempfile
import time
from pathlib import Path

from depguard.agent.loop import AgentLoop
from depguard.agent.patching import apply_patch
from depguard.agent.persistence import persist
from depguard.agent.safety import load_state, sha256_file
from depguard.models.scripted import ScriptedTestModel
from depguard.schemas import to_jsonable


def main():
    output = Path("results/m6")
    output.mkdir(parents=True, exist_ok=True)
    # Each run gets a new directory: never replace previous evidence or user files.
    root = Path(tempfile.mkdtemp(prefix="demo-", dir=output)).resolve()
    source, tests = root / "input.py", root / "test_input.py"
    source.write_bytes(b"result = 1\n")
    tests.write_bytes(b"from solution import result\ndef test_result():\n    assert result == 3\n")
    state = load_state(source, tests, project_root=root)
    original_hash = sha256_file(source)
    test_hash = sha256_file(tests)
    wrong_count = "--- a/input.py\n+++ b/input.py\n@@ -88,77 +99,66 @@\n-result = 1\n+result = 2\n"
    count_example = apply_patch(state, {"patch": wrong_count}, time.monotonic()+10)
    assert count_example.status == "success"
    atomic_before = state.version
    atomic_example = apply_patch(state, {"path": "input.py", "patch":
        "@@\n-result = 2\n+result = 4\n@@\n-missing = 1\n+missing = 2\n"}, 0)
    assert atomic_example.status == "error" and state.version == atomic_before

    # Real M5 two-patch scenario, with M6's deliberately wrong count in the first patch.
    actions = json.loads(Path("examples/m5/script.json").read_text())["actions"]
    for action in actions:
        if action["name"] == "apply_patch":
            action["arguments"]["patch"] = action["arguments"]["patch"].replace("examples/m5/", "")
    actions[1]["arguments"]["patch"] = wrong_count
    state = load_state(source, tests, project_root=root)
    dry_run = AgentLoop(ScriptedTestModel(actions), timeout_seconds=60).run(state, "Return three")
    assert dry_run.final_status == "PASS" and sha256_file(source) == original_hash
    dry_hash_after = sha256_file(source)

    # Separate authorized apply run; adding write permission invalidates old evidence,
    # so rerun from original input with that permission present before validation.
    state = load_state(source, tests, project_root=root,
                       permissions={"read_source", "read_tests", "execute", "write_temp", "write_target"})
    apply_run = AgentLoop(ScriptedTestModel(actions), timeout_seconds=60).run(state, "Return three")
    applied = persist(state, apply_run, deadline=time.monotonic()+30)
    assert applied.applied and source.read_text() == "result = 3\n"

    # Independent input for injected post-write failure, preserving successful apply evidence.
    failed_root = root / "rollback_case"
    failed_root.mkdir()
    failed_source, failed_test = failed_root / "input.py", failed_root / "test_input.py"
    failed_source.write_bytes(b"result = 1\n")
    failed_test.write_bytes(tests.read_bytes())
    failed_state = load_state(failed_source, failed_test, project_root=failed_root,
                             permissions=set(state.permissions))
    failed_run = AgentLoop(ScriptedTestModel(actions), timeout_seconds=60).run(failed_state, "Return three")

    def fail_postcheck(state, deadline):
        raise OSError("M6 demo: injected post-write validation failure")

    restored = persist(failed_state, failed_run, deadline=time.monotonic()+30, validator=fail_postcheck)
    assert restored.persistence["rollback"]["succeeded"]
    assert sha256_file(failed_source) == original_hash and sha256_file(tests) == test_hash
    report = {"provider": "scripted_test", "real_model_quality_claim": False,
              "wrong_count_input": wrong_count, "normalized_count_result": to_jsonable(count_example),
              "atomic_failure": to_jsonable(atomic_example), "atomic_version_unchanged": True,
              "dry_run_sha256_before": original_hash, "dry_run_sha256_after": dry_hash_after,
              "test_sha256_before": test_hash, "test_sha256_after": sha256_file(tests),
              "dry_run": to_jsonable(dry_run), "apply": to_jsonable(applied),
              "postcheck_failure_rollback": to_jsonable(restored)}
    path = root / "report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "dry_run": dry_run.final_status,
                      "apply": applied.applied, "rollback": restored.persistence["rollback"]}, indent=2))


if __name__ == "__main__":
    main()
