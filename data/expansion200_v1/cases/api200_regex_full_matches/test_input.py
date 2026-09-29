import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('ab12 cd3',), ['ab12', 'cd3']), (('none',), []), (('x1x2',), ['x1', 'x2']), (('',), [])])
def test_contract(args, expected):
    assert solve(*args) == expected

