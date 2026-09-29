import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((2, 2), [[0, 0], [0, 0]]), ((0, 3), [])])
def test_contract(args, expected):
    assert solve(*args) == expected


def test_row_independence():
    rows = solve(2, 2)
    rows[0][0] = 1
    assert rows[1] == [0, 0]
