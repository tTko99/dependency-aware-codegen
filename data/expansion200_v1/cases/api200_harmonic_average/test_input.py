import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 1],), 1), (([2, 6],), 3), (([5],), 5), (([3, 3, 3],), 3)])
def test_contract(args, expected):
    assert solve(*args) == expected

