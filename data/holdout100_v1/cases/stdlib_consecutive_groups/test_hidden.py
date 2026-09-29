import solution

def test_contract_0():
    assert solution.solve([]) == []

def test_contract_1():
    assert solution.solve([0, 0, 0]) == [(0, 3)]

def test_contract_2():
    assert solution.solve([2, 1, 2]) == [(2, 1), (1, 1), (2, 1)]
