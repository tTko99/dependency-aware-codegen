import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('a,"b,c",d',), ['a', 'b,c', 'd']), (('"a""b",',), ['a"b', '']), (('',), ['']), (('a,,b',), ['a', '', 'b'])])
def test_contract(args, expected):
    assert solve(*args) == expected

