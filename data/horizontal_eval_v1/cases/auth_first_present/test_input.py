import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([None, 0, 1], 9), 0), (([None, '', 'x'], 9), ''), (([], 9), 9), (([False, True], 9), False)])
def test_contract(args, expected):
    assert solve(*args) == expected

