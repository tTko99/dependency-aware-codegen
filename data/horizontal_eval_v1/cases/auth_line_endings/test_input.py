import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('a\r\nb\rc\n',), ['a', 'b', 'c']), (('',), []), (('a\n\nb',), ['a', '', 'b'])])
def test_contract(args, expected):
    assert solve(*args) == expected

