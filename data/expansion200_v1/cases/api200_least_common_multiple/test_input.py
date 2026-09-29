import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((6, 8), 24), ((-6, 8), 24), ((0, 5), 0), ((7, 7), 7), ((0, 0), 0)])
def test_contract(args, expected):
    assert solve(*args) == expected

