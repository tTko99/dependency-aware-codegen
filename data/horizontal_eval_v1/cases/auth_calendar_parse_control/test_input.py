import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('2024-02-29',), 738945), (('0001-01-01',), 1)])
def test_contract(args, expected):
    assert solve(*args) == expected

def test_error_0():
    with pytest.raises(ValueError):
        solve(*('2023-02-29',))

