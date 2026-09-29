import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((5, 2), 10), ((0, 0), 1), ((8, 0), 1), ((8, 8), 1), ((10, 3), 120)])
def test_contract(args, expected):
    assert solve(*args) == expected

