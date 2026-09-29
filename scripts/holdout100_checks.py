"""Preparation and hidden-evidence separation checks; no model inference."""
import ast

from scripts.holdout100_prepare import mutations, verify_agent
from scripts.holdout100_prepare import test_text as render_tests
from scripts.holdout100_run import visible_case


def test_agent_freeze_unchanged():
    assert verify_agent()['model_identity']['model']=='qwen3-coder:30b'


def test_visible_projection_excludes_reference_and_hidden():
    case={'id':'x','code_file':'input.py','test_file':'visible.py','requirement':'contract',
          'reference_file':'SECRET_REFERENCE','hidden_test_file':'SECRET_TEST','hashes':{'secret':'x'},
          'provenance':{'secret':'y'}}
    visible=visible_case(case)
    assert set(visible)=={'id','code_file','test_file','requirement'}
    assert 'SECRET' not in str(visible)


def test_assertion_conversion_preserves_expectation():
    text=render_tests(['assert f(2) == 4'],'def f(n):\n    return n*2\n')
    assert 'solution.f(2) == 4' in text
    assert 'return n' not in text
    ast.parse(text)


def test_mutations_deterministic_and_bounded():
    source='def f(n):\n    return n+1 if n>0 else n-1\n'
    first=mutations(source,123)
    assert first==mutations(source,123) and 0<len(first)<=16
    assert len({row[1] for row in first})==len(first)
    for _,code,_ in first:
        ast.parse(code)
        assert 'def f(n)' in code


def test_hidden_acceptance_uses_final_candidate_without_model(tmp_path):
    from scripts.holdout100_run import final_acceptance
    source=tmp_path/'input.py';hidden=tmp_path/'test_hidden.py'
    source.write_text('result = 1\n')
    hidden.write_text('from solution import result\ndef test_hidden():\n    assert result == 2\n')
    case={'code_file':str(source),'hidden_test_file':str(hidden),'required_checks':['run_pytest']}
    result=final_acceptance(case,{'candidate_code':'result = 2\n'})
    assert result['status']=='PASS' and result['model_feedback'] is False
    assert source.read_text()=='result = 1\n'
    assert final_acceptance(case,{'candidate_code':'result = 3\n'})['status']=='FAIL'


def test_all_authored_assertions_parse_and_splits_are_disjoint():
    from scripts.holdout100_authored import specs
    for spec in specs():
        sets=[]
        for part in ['visible','hidden']:
            tree=ast.parse(render_tests(spec[part],spec['reference']))
            sets.append({ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Assert)})
        assert sets[0] and sets[1] and not sets[0]&sets[1],spec['id']
