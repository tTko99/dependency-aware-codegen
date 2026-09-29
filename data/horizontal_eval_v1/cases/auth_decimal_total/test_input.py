import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((['0.1', '0.2'],), '0.3'), (([],), '0'), ((['100000000000000000000', '1'],), '100000000000000000001')])
def test_contract(args, expected):
    assert solve(*args) == expected

