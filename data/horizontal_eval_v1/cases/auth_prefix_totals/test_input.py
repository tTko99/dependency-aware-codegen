import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([2, -1, 4],), [2, 1, 5]), (([],), []), (([0],), [0])])
def test_contract(args, expected):
    assert solve(*args) == expected

