import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('12', 0), 12), (('bad', 7), 7), ((None, 3), 3), (('-2', 0), -2)])
def test_contract(args, expected):
    assert solve(*args) == expected

