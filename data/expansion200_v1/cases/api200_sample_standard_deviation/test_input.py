import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 3],), 1.414214), (([2, 2, 2],), 0), (([1, 2, 3],), 1)])
def test_contract(args, expected):
    assert solve(*args) == expected

