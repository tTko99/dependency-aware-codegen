import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((10, 3), 4), ((0, 7), 0), ((12, 4), 3), ((100000000000000000001, 10), 10000000000000000001)])
def test_contract(args, expected):
    assert solve(*args) == expected

