import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('valid_2',), True), (('a!',), False), (('a\n',), False), (('2a',), False), (('',), False)])
def test_contract(args, expected):
    assert solve(*args) == expected

