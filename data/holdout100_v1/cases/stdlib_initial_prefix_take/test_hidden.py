import solution

def test_contract_0():
    assert solution.solve([0, 1, 2], 3) == [0, 1, 2]

def test_contract_1():
    assert solution.solve([], 0) == []

def test_contract_2():
    assert solution.solve([1, 2, 2, 0], 2) == [1]
