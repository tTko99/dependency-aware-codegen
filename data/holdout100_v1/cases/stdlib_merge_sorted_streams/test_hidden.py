import solution

def test_contract_0():
    assert solution.solve([], [-1, 0]) == [-1, 0]

def test_contract_1():
    assert solution.solve([-3, 0], [-2, 1]) == [-3, -2, 0, 1]

def test_contract_2():
    assert solution.solve([], []) == []
