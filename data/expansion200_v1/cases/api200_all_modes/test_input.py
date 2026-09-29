import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 2, 1, 2, 3],), [1, 2]), (([3, 2, 3],), [3]), (([],), []), (([4, 5],), [4, 5])])
def test_contract(args, expected):
    assert solve(*args) == expected

