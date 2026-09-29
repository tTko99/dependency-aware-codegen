import solution

def test_contract_0():
    assert solution.is_sublist([2, 4, 3, 5, 7], [3, 7]) == False

def test_contract_1():
    assert solution.is_sublist([2, 4, 3, 5, 7], [4, 3]) == True
