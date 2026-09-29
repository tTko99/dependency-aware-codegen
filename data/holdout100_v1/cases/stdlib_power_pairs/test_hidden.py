import solution

def test_contract_0():
    assert solution.solve([]) == []

def test_contract_1():
    assert solution.solve([(-2, 3), (4, 2)]) == [-8, 16]

def test_contract_2():
    assert solution.solve([(10, -1)]) == [0.1]
