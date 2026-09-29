import solution

def test_contract_0():
    assert solution.find_Odd_Pair([5, 4, 7, 2, 1], 5) == 6

def test_contract_1():
    assert solution.find_Odd_Pair([7, 2, 8, 1, 0, 5, 11], 7) == 12
