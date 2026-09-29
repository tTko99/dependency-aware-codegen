import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 2, 3],), (3, 6)), (([],), (0, 0))])
def test_contract(args, expected):
    assert solve(*args) == expected


def test_iterator_consumed_once():
    assert solve(iter([1, 2, 3])) == (3, 6)
