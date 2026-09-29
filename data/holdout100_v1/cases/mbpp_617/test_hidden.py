import solution

def test_contract_0():
    assert solution.min_Jumps((11, 14), 11) == 1

def test_contract_1():
    assert solution.min_Jumps((3, 4), 11) == 3.5
