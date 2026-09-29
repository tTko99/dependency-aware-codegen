import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(({'a': 1, 'b': 2}, {'a': 2}), {'a': -1, 'b': 2}), (({'a': 1}, {'a': 1}), {'a': 0}), (({}, {'x': 2}), {'x': -2}), (({}, {}), {})])
def test_contract(args, expected):
    assert solve(*args) == expected

