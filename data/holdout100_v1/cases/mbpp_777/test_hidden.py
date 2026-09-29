import solution

def test_contract_0():
    assert solution.find_sum([1, 2, 3, 1, 1, 4, 5, 6]) == 21

def test_contract_1():
    assert solution.find_sum([1, 10, 9, 4, 2, 10, 10, 45, 4]) == 71
