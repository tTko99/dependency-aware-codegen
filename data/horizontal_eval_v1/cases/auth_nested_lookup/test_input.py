import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(({'a': {'b': 0}}, ['a', 'b'], 9), 0), (({'a': None}, ['a'], 9), None), (({'a': 1}, ['a', 'b'], 9), 9), (({'x': 2}, [], 9), {'x': 2})])
def test_contract(args, expected):
    assert solve(*args) == expected

