import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([3, 1, 2],), [1, 2, 3]), (([],), [])])
def test_contract(args, expected):
    assert solve(*args) == expected


def test_does_not_mutate():
    values = [3, 1, 2]
    assert solve(values) == [1, 2, 3]
    assert values == [3, 1, 2]
