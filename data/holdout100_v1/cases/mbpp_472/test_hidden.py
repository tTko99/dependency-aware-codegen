import solution

def test_contract_0():
    assert solution.check_Consecutive([1, 2, 3, 4, 5]) == True

def test_contract_1():
    assert solution.check_Consecutive([1, 2, 1]) == False
