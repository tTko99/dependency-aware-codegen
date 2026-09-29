import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([2, 3, 4],), 24), (([],), 1), (([0, 5],), 0), (([-2, 3],), -6)])
def test_contract(args, expected):
    assert solve(*args) == expected

