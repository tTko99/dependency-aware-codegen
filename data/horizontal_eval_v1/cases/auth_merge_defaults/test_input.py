import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(({'a': 1, 'b': 2}, {'a': 0}), {'a': 0, 'b': 2}), (({'x': True}, {'x': False}), {'x': False}), (({}, {'x': None}), {'x': None})])
def test_contract(args, expected):
    assert solve(*args) == expected

