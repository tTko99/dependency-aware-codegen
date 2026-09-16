import time

import pytest

from depguard.agent.contracts import ToolCall
from depguard.agent.loop import AgentLoop
from depguard.agent.regression import regression_guard
from depguard.agent.safety import load_state, risk_findings
from depguard.agent.tools import default_registry, run_pytest
from depguard.models.scripted import ScriptedTestModel


def state_at(tmp_path, code="result = 1\n", **options):
    source = tmp_path / "input.py"
    source.write_text(code)
    tests = tmp_path / "test_input.py"
    tests.write_text("from solution import result\ndef test_result():\n    assert result == 1\n")
    return load_state(source, tests, project_root=tmp_path, **options)


@pytest.mark.parametrize("code", [
    "import subprocess as s\ns.run(['whoami'])", "from os import system as f\nf('whoami')",
    "eval('1')", "exec('1')", "import shutil as s\ns.rmtree('x')",
    "open('x', 'w').write('x')", "import requests as r\nr.post('https://example.com')",
    "import os as o\nf=getattr(o, 'sys' + 'tem')\ng=f\ng('whoami')",
])
def test_risk_refusal_before_execution(tmp_path, code):
    state = state_at(tmp_path, code)
    result = default_registry().dispatch(state, ToolCall("execute"), deadline=time.monotonic()+5)
    assert result.status == "denied" and result.evidence["error_code"] == "REQUIRES_SANDBOX"
    assert result.evidence["executed"] is False and not state.passed_checks


def test_static_getattr_resolves_constant_concatenation():
    findings = risk_findings("import os as o\nf=getattr(o, 'sys'+'tem')\nf('x')")
    assert any(f["detail"] == "os.system" and f["reason"] == "dangerous_call" for f in findings)
    assert any(f["reason"] == "dynamic_attribute" for f in risk_findings("getattr(obj, 'method')()"))


def test_syntax_repair_is_not_blocked_by_broken_original(tmp_path):
    state = state_at(tmp_path, "def broken(:\n")
    state.candidate_code = "result = 1\n"
    report = regression_guard(state)
    assert not report["blocked"]
    assert any(f["code"] == "ORIGINAL_SYNTAX_UNAVAILABLE" for f in report["findings"])


def test_test_integrity_inside_direct_tool(tmp_path):
    state = state_at(tmp_path)
    state.test_path.write_text("# changed\n")
    result = run_pytest(state, {}, time.monotonic()+5)
    assert result.evidence["error_code"] == "TEST_INTEGRITY_MISMATCH"


def test_config_integrity(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    state = state_at(tmp_path, config_paths=[config])
    config.write_text('{"changed": true}')
    result = run_pytest(state, {}, time.monotonic()+5)
    assert result.evidence["error_code"] == "CONFIG_INTEGRITY_MISMATCH"


@pytest.mark.parametrize("code", ["pytest.skip('x')", "pytest.mark.skipif(True)",
                                 "pytest.xfail('x')", "pytest.mark.xfail()"])
def test_regression_skip_aliases(tmp_path, code):
    state = state_at(tmp_path)
    state.candidate_code += "import pytest as p\n" + code.replace("pytest", "p") + "\n"
    report = regression_guard(state)
    assert report["blocked"] and any(f["code"] == "TEST_BYPASS" for f in report["findings"])


def test_public_deletion_and_size_limits(tmp_path):
    state = state_at(tmp_path, "def public():\n    return 1\nclass Public:\n    pass\n")
    state.candidate_code = "result = 1\n"
    state.regression_config = {"max_patch_lines": 1, "max_files": 0}
    report = regression_guard(state)
    assert {f["code"] for f in report["findings"]} >= {
        "PUBLIC_API_REMOVED", "PATCH_SIZE_EXCEEDED", "FILE_COUNT_EXCEEDED"}


def test_warning_is_not_proof_of_cheating(tmp_path):
    state = state_at(tmp_path, "result = sum([1])\n")
    state.candidate_code = "try:\n    result = 1\nexcept Exception:\n    pass\n"
    report = regression_guard(state)
    assert not report["blocked"]
    assert {f["code"] for f in report["findings"]} == {
        "EXCEPTION_SUPPRESSED", "ASSERTION_CONSTANT_MATCH"}


def test_severe_guard_blocks_finish_even_with_passed_checks(tmp_path):
    state = state_at(tmp_path, "def public():\n    return 1\nresult = 1\n")
    state.candidate_code = "result = 1\n"
    actions = [{"name": n} for n in ["validate_packages", "validate_apis", "execute", "run_pytest"]]
    actions.append({"name": "finish", "arguments": {"success": True}})
    run = AgentLoop(ScriptedTestModel(actions), max_steps=len(actions)).run(state, "")
    assert run.final_status == "INCOMPLETE" and run.rejected_finish_count == 1
    assert not run.finish_verification["missing_checks"] and run.regression_guard["blocked"]
