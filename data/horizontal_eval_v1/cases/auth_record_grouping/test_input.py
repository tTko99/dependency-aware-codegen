import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([{'kind': 'a', 'n': 1}, {'kind': 'a', 'n': 2}],), {'a': [{'kind': 'a', 'n': 1}, {'kind': 'a', 'n': 2}]}), (([{'n': 1}],), {None: [{'n': 1}]}), (([],), {})])
def test_contract(args, expected):
    assert solve(*args) == expected

