import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([0, 1, False, 2], None), ([0, False], [1, 2])), (([1, 2, 3, 4], 'even'), ([1, 3], [2, 4])), (([], None), ([], []))])
def test_contract(args, expected):
    assert solve(*args) == expected

