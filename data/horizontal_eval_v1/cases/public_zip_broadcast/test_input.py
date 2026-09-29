import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([[1, 2], 'x'], True), [(1, 'x'), (2, 'x')]), (([2, 'x'], True), [(2, 'x')]), (([], True), []), (([[1, 2], [3]], False), [(1, 3)])])
def test_contract(args, expected):
    assert solve(*args) == expected

def test_error_0():
    with pytest.raises(ValueError):
        solve(*([[1, 2], [3]], True))

def test_error_1():
    with pytest.raises(ValueError):
        solve(*([[1], [2, 3]], True))

