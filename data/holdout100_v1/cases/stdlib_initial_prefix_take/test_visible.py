import solution

def test_contract_0():
    assert solution.solve([1, 4, 2], 3) == [1]

def test_contract_1():
    assert solution.solve([4, 1], 3) == []
