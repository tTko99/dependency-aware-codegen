import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('a,b;c',), ['a', 'b', 'c']), (('a,,b;',), ['a', '', 'b', '']), (('',), ['']), (('abc',), ['abc'])])
def test_contract(args, expected):
    assert solve(*args) == expected

