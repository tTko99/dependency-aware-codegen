import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('$a $b', {'a': 'yes'}), 'yes $b'), (('$$${x}', {'x': 3}), '$3'), (('plain', {}), 'plain'), (('$missing', {}), '$missing')])
def test_contract(args, expected):
    assert solve(*args) == expected

