import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([[1, 2], [3, 4]],), [[1, 3], [2, 4]]), (([],), []), (([[], []],), [])])
def test_contract(args, expected):
    assert solve(*args) == expected

def test_error_0():
    with pytest.raises(ValueError):
        solve(*([[1, 2], [3]],))

