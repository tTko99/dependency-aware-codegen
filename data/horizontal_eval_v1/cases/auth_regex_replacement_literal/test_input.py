import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('a1b2', '\\d', '\\1'), 'a\\1b\\1'), (('aaa', 'a', '$'), '$$$'), (('abc', 'z', 'x'), 'abc')])
def test_contract(args, expected):
    assert solve(*args) == expected

