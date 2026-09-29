import solution

def test_contract_0():
    assert solution.sum_range_list([2, 1, 5, 6, 8, 3, 4, 9, 10, 11, 8, 12], 8, 10) == 29

def test_contract_1():
    assert solution.sum_range_list([2, 1, 5, 6, 8, 3, 4, 9, 10, 11, 8, 12], 5, 7) == 16
