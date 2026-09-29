import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((0, 0.0001, 0.001), True), ((1000, 1001, 0.01), False), ((2, 2, 0), True), ((-1, 1, 2), True)])
def test_contract(args, expected):
    assert solve(*args) == expected

