import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((1900,), False), ((2000,), True), ((2024,), True), ((2023,), False), ((2100,), False)])
def test_contract(args, expected):
    assert solve(*args) == expected

