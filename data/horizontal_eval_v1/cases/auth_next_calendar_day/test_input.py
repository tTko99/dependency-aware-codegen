import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('2024-02-28',), '2024-02-29'), (('2024-02-29',), '2024-03-01'), (('2023-12-31',), '2024-01-01')])
def test_contract(args, expected):
    assert solve(*args) == expected

