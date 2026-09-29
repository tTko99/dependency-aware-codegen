import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([4, 5, 6], [2, 0]), (6, 4)), ((['a', 'b'], [0, 0]), ('a', 'a')), (([1, 2, 3], [-1, 1]), (3, 2))])
def test_contract(args, expected):
    assert solve(*args) == expected

