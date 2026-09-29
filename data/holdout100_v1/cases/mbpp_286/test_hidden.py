import solution

def test_contract_0():
    assert solution.max_sub_array_sum_repeated([-1, -2, -3], 3, 3) == -1

def test_contract_1():
    assert solution.max_sub_array_sum_repeated([10, 20, -30, -1], 4, 3) == 30
