import solution

def test_contract_0():
    assert solution.solve([1, 4, 2, 5], 3) == [4, 2, 5]

def test_contract_1():
    assert solution.solve([0, 1], 3) == []
