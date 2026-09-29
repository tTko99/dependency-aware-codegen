import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 2, 3],), [(1, 2), (2, 3)]), (([],), []), (([7],), []), (([4, 4],), [(4, 4)])])
def test_contract(args, expected):
    assert solve(*args) == expected

