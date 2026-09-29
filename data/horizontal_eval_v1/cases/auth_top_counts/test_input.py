import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((['b', 'a', 'b', 'c', 'a'], 2), [('b', 2), ('a', 2)]), (([], 3), []), ((['x'], 0), [])])
def test_contract(args, expected):
    assert solve(*args) == expected

