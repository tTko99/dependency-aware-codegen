import solution

def test_contract_0():
    assert solution.unique_product([10, 20, 30, 40, 20, 50, 60, 40]) == 720000000

def test_contract_1():
    assert solution.unique_product([7, 8, 9, 0, 1, 1]) == 0
