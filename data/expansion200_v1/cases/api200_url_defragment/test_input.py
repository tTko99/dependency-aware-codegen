import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('https://a/x?q=1#part',), 'https://a/x?q=1'), (('a%23b#c',), 'a%23b'), (('plain',), 'plain'), (('',), '')])
def test_contract(args, expected):
    assert solve(*args) == expected

