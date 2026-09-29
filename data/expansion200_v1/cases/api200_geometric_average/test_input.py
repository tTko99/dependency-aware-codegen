import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 16],), 4), (([2, 8],), 4), (([5],), 5), (([1, 1, 1],), 1)])
def test_contract(args, expected):
    assert solve(*args) == expected

