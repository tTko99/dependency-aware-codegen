import solution

def test_contract_0():
    assert solution.find_min_diff((1, 5, 3, 19, 18, 25), 6) == 1

def test_contract_1():
    assert solution.find_min_diff((4, 3, 2, 6), 4) == 1
