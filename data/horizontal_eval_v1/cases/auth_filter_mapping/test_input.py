import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(({'a': None, 'b': 0, 'c': False},), {'b': 0, 'c': False}), (({},), {})])
def test_contract(args, expected):
    assert solve(*args) == expected


def test_original_preserved():
    values = {'a': None, 'b': 2}
    assert solve(values) == {'b': 2}
    assert values == {'a': None, 'b': 2}
