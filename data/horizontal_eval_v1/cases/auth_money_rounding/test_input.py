import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('1.005',), '1.01'), (('-1.005',), '-1.01'), (('3',), '3.00'), (('2.674',), '2.67')])
def test_contract(args, expected):
    assert solve(*args) == expected

