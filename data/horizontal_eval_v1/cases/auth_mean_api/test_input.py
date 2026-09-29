import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([2, 4, 9],), 5), (([-2, 2],), 0), (([3],), 3)])
def test_contract(args, expected):
    assert solve(*args) == expected

