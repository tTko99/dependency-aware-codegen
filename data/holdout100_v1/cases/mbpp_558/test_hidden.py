import solution

def test_contract_0():
    assert solution.digit_distance_nums(123, 256) == 7

def test_contract_1():
    assert solution.digit_distance_nums(23, 56) == 6
