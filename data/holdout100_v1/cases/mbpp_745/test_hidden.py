import solution

def test_contract_0():
    assert solution.divisible_by_digits(1, 22) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 15, 22]

def test_contract_1():
    assert solution.divisible_by_digits(20, 25) == [22, 24]
