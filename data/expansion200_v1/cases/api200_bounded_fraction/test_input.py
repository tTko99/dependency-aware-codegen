import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('0.3333333', 10), (1, 3)), (('3.14159', 10), (22, 7)), (('0', 5), (0, 1)), (('-0.5', 10), (-1, 2))])
def test_contract(args, expected):
    assert solve(*args) == expected

