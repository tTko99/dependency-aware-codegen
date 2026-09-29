import solution

def test_contract_0():
    assert solution.solve([1, 4], [2, 3]) == [1, 2, 3, 4]

def test_contract_1():
    assert solution.solve([2, 2], [1, 2]) == [1, 2, 2, 2]
