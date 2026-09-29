import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 4],), 1), (([5, 1, 3],), 3), (([9],), 9), (([6, 2, 4, 8],), 4)])
def test_contract(args, expected):
    assert solve(*args) == expected

