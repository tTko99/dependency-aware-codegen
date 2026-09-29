import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('{"a":1,"a":2}',), [('a', 1), ('a', 2)]), (('{}',), []), (('{"b":false,"x":null}',), [('b', False), ('x', None)])])
def test_contract(args, expected):
    assert solve(*args) == expected

