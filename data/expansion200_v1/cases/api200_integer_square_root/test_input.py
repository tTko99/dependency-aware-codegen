import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((0,), 0), ((15,), 3), ((16,), 4), ((9999999999999999999999999999999999999999,), 99999999999999999999)])
def test_contract(args, expected):
    assert solve(*args) == expected

