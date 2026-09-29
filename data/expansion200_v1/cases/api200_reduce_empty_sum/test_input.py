import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([],), 0), (([1, 2, 3],), 6), (([-1, 1],), 0), (([8],), 8)])
def test_contract(args, expected):
    assert solve(*args) == expected

