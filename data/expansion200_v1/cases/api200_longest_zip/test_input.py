import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 2], [3], 0), [(1, 3), (2, 0)]), (([], [3], None), [(None, 3)]), (([], [], 0), []), (([1], [2, 3], -1), [(1, 2), (-1, 3)])])
def test_contract(args, expected):
    assert solve(*args) == expected

