import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('a=1&a=2&b=',), {'a': ['1', '2'], 'b': ['']}), (('q=a+b&x=%2B',), {'q': ['a b'], 'x': ['+']}), (('',), {})])
def test_contract(args, expected):
    assert solve(*args) == expected

