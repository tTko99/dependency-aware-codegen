import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((1, 3), (1, 3)), ((-2, -4), (1, 2)), ((0, 5), (0, 1)), ((10, 6), (5, 3))])
def test_contract(args, expected):
    assert solve(*args) == expected

