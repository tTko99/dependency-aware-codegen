import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('A  a\tB\n',), {'a': 2, 'b': 1}), (('Straße STRASSE',), {'strasse': 2}), (('',), {})])
def test_contract(args, expected):
    assert solve(*args) == expected

