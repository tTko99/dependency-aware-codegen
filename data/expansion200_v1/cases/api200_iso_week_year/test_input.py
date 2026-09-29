import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((2021, 1, 1), (2020, 53, 5)), ((2024, 1, 1), (2024, 1, 1)), ((2020, 12, 31), (2020, 53, 4))])
def test_contract(args, expected):
    assert solve(*args) == expected

