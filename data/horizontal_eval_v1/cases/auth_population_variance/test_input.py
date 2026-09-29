import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 3],), 1), (([7],), 0), (([2, 2, 2],), 0)])
def test_contract(args, expected):
    assert solve(*args) == expected

