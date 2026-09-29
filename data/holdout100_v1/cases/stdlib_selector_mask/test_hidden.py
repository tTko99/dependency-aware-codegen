import solution

def test_contract_0():
    assert solution.solve(['x', 'y', 'z'], [0, 1]) == ['y']

def test_contract_1():
    assert solution.solve([], [1]) == []

def test_contract_2():
    assert solution.solve([1, 2], [False, True, True]) == [2]
