import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('  a\n    b\n',), 'a\n  b\n'), (('x',), 'x'), (('',), ''), (('    a\n    b',), 'a\nb')])
def test_contract(args, expected):
    assert solve(*args) == expected

