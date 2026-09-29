import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('foobar', 'foo'), 'bar'), (('ofobar', 'foo'), 'ofobar'), (('foofoo', 'foo'), 'foo'), (('abc', ''), 'abc')])
def test_contract(args, expected):
    assert solve(*args) == expected

