import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((5, 2), 20), ((0, 0), 1), ((8, 0), 1), ((4, 4), 24), ((10, 3), 720)])
def test_contract(args, expected):
    assert solve(*args) == expected

