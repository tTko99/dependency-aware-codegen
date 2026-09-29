import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([{'id': 1, 'v': 'a'}, {'id': 1, 'v': 'b'}, {'id': 2, 'v': 'c'}],), [{'id': 1, 'v': 'a'}, {'id': 2, 'v': 'c'}]), (([],), [])])
def test_contract(args, expected):
    assert solve(*args) == expected

