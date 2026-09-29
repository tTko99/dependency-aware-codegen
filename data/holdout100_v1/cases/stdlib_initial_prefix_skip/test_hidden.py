import solution

def test_contract_0():
    assert solution.solve([5, 0, 1], 4) == [5, 0, 1]

def test_contract_1():
    assert solution.solve([], 2) == []

def test_contract_2():
    assert solution.solve([2, 2, 3, 1], 3) == [3, 1]
