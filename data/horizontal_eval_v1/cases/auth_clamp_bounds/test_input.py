import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((5, 0, 10), 5), ((-2, 0, 10), 0), ((20, 0, 10), 10), ((3, 2, 2), 2)])
def test_contract(args, expected):
    assert solve(*args) == expected

def test_error_0():
    with pytest.raises(ValueError):
        solve(*(1, 3, 2))

