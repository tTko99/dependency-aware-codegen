import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([{'score': '10'}, {'score': '2'}, {'score': '-1'}],), [{'score': '-1'}, {'score': '2'}, {'score': '10'}]), (([],), [])])
def test_contract(args, expected):
    assert solve(*args) == expected

