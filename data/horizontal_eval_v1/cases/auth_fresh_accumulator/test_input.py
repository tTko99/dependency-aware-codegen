import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [((1,), [1]), ((2,), [2]), ((3, [0]), [0, 3])])
def test_contract(args, expected):
    assert solve(*args) == expected


def test_independent_calls():
    assert solve('x') == ['x']
    assert solve('y') == ['y']
    original = [0]
    assert solve(1, original) == [0, 1]
    assert original == [0]
