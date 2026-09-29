import time

import pytest

from depguard.agent.contracts import ToolCall
from depguard.agent.loop import AgentLoop
from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry
from depguard.models.scripted import ScriptedTestModel


def state_at(tmp_path):
    source, tests = tmp_path / 'input.py', tmp_path / 'test_input.py'
    source.write_text('result = 1\n')
    tests.write_text('from solution import result\ndef test_result():\n    assert result == 2\n')
    return load_state(source, tests, project_root=tmp_path)


def invoke(state, name='replace_candidate', **args):
    return default_registry().dispatch(state, ToolCall(name, args), deadline=time.monotonic()+15)


def test_replace_invalidates_checks_and_rollback_restores(tmp_path):
    state = state_at(tmp_path)
    validate_candidate(state, time.monotonic()+15)
    version = state.version
    result = invoke(state, code='result = 2\n', expected_version=version)
    assert result.status == 'success' and state.candidate_revision == 1
    assert set(result.evidence['validation_state']['required_checks'].values()) == {'stale'}
    assert not state.cache and not state.passed_checks
    assert state.source_path.read_text() == 'result = 1\n'
    assert state.applied_patches == [result.evidence['normalized_patch']]
    invoke(state, 'rollback')
    assert state.candidate_code == state.original_code


@pytest.mark.parametrize('code,error', [('', 'REPLACEMENT_EMPTY'),
    ('def broken(:', 'REPLACEMENT_SYNTAX_ERROR'),
    ('```python\nresult = 2\n```', 'REPLACEMENT_SYNTAX_ERROR'),
    ('result = 1\n', 'REPLACEMENT_NO_CHANGE')])
def test_rejected_replacement_atomic(tmp_path, code, error):
    state = state_at(tmp_path)
    version = state.version
    result = invoke(state, code=code, expected_version=version)
    assert result.evidence['error_code'] == error
    assert state.version == version and not state.candidate_history


def test_stale_version_and_integrity_and_permissions(tmp_path):
    state = state_at(tmp_path)
    assert invoke(state, code='result = 2\n', expected_version='old').status == 'error'
    state.source_path.write_text('result = 9\n')
    assert invoke(state, code='result = 2\n', expected_version=state.version).status == 'denied'
    state.permissions.clear()
    assert invoke(state, code='result = 2\n', expected_version=state.version).status == 'denied'
    assert state.candidate_revision == 0


def test_replacement_does_not_bypass_execution_safety(tmp_path):
    state = state_at(tmp_path)
    assert invoke(state, code='import os\nos.system("echo unsafe")\n',
                  expected_version=state.version).status == 'success'
    assert invoke(state, 'execute').status == 'denied'


def test_model_replaces_then_validates_and_finishes(tmp_path):
    state = state_at(tmp_path)
    actions = [{'name': 'replace_candidate', 'arguments': {
        'code': 'result = 2\n', 'expected_version': state.version}}]
    actions += [{'name': n, 'arguments': {}} for n in
                ['run_pytest', 'validate_packages', 'validate_apis', 'execute']]
    actions += [{'name': 'finish', 'arguments': {'success': True}}]
    result = AgentLoop(ScriptedTestModel(actions)).run(state, 'Return 2')
    assert result.final_status == 'PASS'
    assert state.source_path.read_text() == 'result = 1\n'
