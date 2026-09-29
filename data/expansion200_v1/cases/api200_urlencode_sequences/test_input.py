import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([('a', [1, 2]), ('b', 'x y')],), 'a=1&a=2&b=x+y'), (([('a', [])],), ''), (([],), ''), (([('q', '+')],), 'q=%2B')])
def test_contract(args, expected):
    assert solve(*args) == expected

