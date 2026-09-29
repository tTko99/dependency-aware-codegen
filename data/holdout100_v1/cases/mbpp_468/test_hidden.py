import solution

def test_contract_0():
    assert solution.max_product([4, 42, 55, 68, 80]) == 50265600

def test_contract_1():
    assert solution.max_product([3, 100, 4, 5, 150, 6]) == 3000
