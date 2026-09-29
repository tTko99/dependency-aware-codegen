import solution

def test_contract_0():
    assert solution.solve([1, 2], 2) == [(1, 1), (1, 2), (2, 2)]

def test_contract_1():
    assert solution.solve([4], 2) == [(4, 4)]
