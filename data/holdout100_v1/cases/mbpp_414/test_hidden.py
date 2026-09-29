import solution

def test_contract_0():
    assert solution.overlapping([1, 4, 5], [1, 4, 5]) == True

def test_contract_1():
    assert solution.overlapping([1, 2, 3], [4, 5, 6]) == False
