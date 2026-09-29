import solution

def test_contract_0():
    assert solution.all_unique([1, 2, 3, 4, 5]) == True

def test_contract_1():
    assert solution.all_unique([1, 2, 1, 2]) == False
