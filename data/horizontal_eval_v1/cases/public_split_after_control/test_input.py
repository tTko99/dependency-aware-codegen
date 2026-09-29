import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([1, 0], 1), [[1, 0]]), (([1, 0, 2, 0, 3], 1), [[1, 0], [2, 0, 3]]), (([], -1), []), (([0, 0], -1), [[0], [0]])])
def test_contract(args, expected):
    assert solve(*args) == expected

