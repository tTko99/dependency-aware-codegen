import solution

def test_contract_0():
    assert solution.max_subarray_product([1, -2, -3, 0, 7, -8, -2]) == 112

def test_contract_1():
    assert solution.max_subarray_product([-2, -40, 0, -2, -3]) == 80
