import time

import pytest

from depguard.agent.contracts import ToolCall
from depguard.agent.safety import load_state, risk_findings
from depguard.agent.tools import default_registry, run_pytest


@pytest.mark.parametrize("code", [
    "import subprocess as s\ns.run(['echo', 'oops'])",
    "from os import system as f\ng=f\ng('echo bad')",
    "f=eval\nf('1+1')", "exec('print(1)')",
    "import requests as r\nr.post('https://example.com')",
    "from pathlib import Path as P\np=P('file')\nf=p.write_text\nf('x')",
    "import shutil as s\ns.rmtree('x')",
    "import os\nf=getattr(os, 'system')\nf('x')",
    "getattr(obj, name)()", "obj.__class__.__bases__",
    "__import__('os').system('x')", "callbacks[0]()",
])
def test_risk_aliases_and_dynamic_calls(code):
    assert risk_findings(code)


def make_state(tmp_path, **options):
    source, tests = tmp_path / "input.py", tmp_path / "test_input.py"
    source.write_text("result=1\n")
    tests.write_text("from solution import result\ndef test_result():\n    assert result == 1\n")
    return load_state(source, tests, project_root=tmp_path, **options)


def dispatch(state, name):
    return default_registry().dispatch(state, ToolCall(name), deadline=time.monotonic() + 5)


@pytest.mark.parametrize("which", ["source_path", "test_path"])
def test_inputs_rehashed_inside_tool(tmp_path, which):
    state = make_state(tmp_path)
    getattr(state, which).write_text("result=2\n")
    result = dispatch(state, "run_pytest")
    assert result.status == "denied"
    assert result.evidence["expected"] != result.evidence["actual"]
    assert run_pytest(state, {}, time.monotonic()+5).status == "denied"


def test_cached_validation_cannot_bypass_hash_or_permission(tmp_path):
    state = make_state(tmp_path)
    registry = default_registry()
    call = ToolCall("validate_packages")
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "success"
    state.permissions.remove("read_source")
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "denied"
    state.permissions.add("read_source")
    state.test_path.write_text("# changed")
    assert registry.dispatch(state, call, deadline=time.monotonic()+5).status == "denied"


@pytest.mark.parametrize("policy,status", [("reject", "denied"), ("mock", "mock"),
                                          ("requires_sandbox", "denied")])
def test_test_code_is_screened_and_never_runs(tmp_path, policy, status):
    state = make_state(tmp_path, risk_policy=policy)
    # Construct a fresh frozen test input with a side effect.
    state.test_path.write_text("open('sentinel', 'w').write('bad')\n")
    state = load_state(state.source_path, state.test_path, project_root=tmp_path, risk_policy=policy)
    result = dispatch(state, "run_pytest")
    assert result.status == status
    assert result.evidence["executed"] is False
    assert "run_pytest" not in state.passed_checks
    assert not (tmp_path / "sentinel").exists()


def test_execute_and_temp_permissions(tmp_path):
    for permission in ("execute", "write_temp", "read_tests"):
        state = make_state(tmp_path)
        state.permissions.remove(permission)
        assert dispatch(state, "run_pytest").status == "denied"


def test_sanity_risks_are_limited_to_hallucinated_imports():
    from pathlib import Path

    root = Path("data/engineering_sanity/cases")
    for file in root.glob("*/*.py"):
        findings = risk_findings(file.read_text())
        # A hallucinated package is conservatively refused, never imported.
        assert all(f["reason"] in {"untrusted_import", "network", "unresolved_call"}
                   for f in findings), (file, findings)
