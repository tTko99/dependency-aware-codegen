import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 2, 2, 4], 2), 3), (([], 3), 0), (([1, 4], 0), 0), (([1, 4], 8), 2)])
def test_contract(args, expected):
    assert solve(*args) == expected

