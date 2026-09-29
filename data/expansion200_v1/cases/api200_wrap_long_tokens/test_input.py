import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('abcdefgh xy', 4), ['abcdefgh', 'xy']), (('ab-cd ef', 4), ['ab-cd', 'ef']), (('', 3), []), (('a bb c', 4), ['a bb', 'c'])])
def test_contract(args, expected):
    assert solve(*args) == expected

