import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 4, 4, 2], 3), [4, 4, 2]), (([1, 2], 0), []), (([], 3), []), (([1, 2], 5), [2, 1])])
def test_contract(args, expected):
    assert solve(*args) == expected

