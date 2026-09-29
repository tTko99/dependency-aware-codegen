import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(([[1, 2], [], [3]],), [1, 2, 3]), (([],), []), (([['ab'], ['cd']],), ['ab', 'cd']), (([[[1]], [2]],), [[1], 2])])
def test_contract(args, expected):
    assert solve(*args) == expected

