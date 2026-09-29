import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([], -1), []), (([1, -2, 3, -4], -1), [[1], [-2, 3], [-4]]), (([-1, 2, -3, 4], 1), [[-1, 2], [-3, 4]]), (([], 0), [[]])])
def test_contract(args, expected):
    assert solve(*args) == expected

