import solution

def test_contract_0():
    assert solution.multiply_elements((2, 4, 5, 6, 7)) == (8, 20, 30, 42)

def test_contract_1():
    assert solution.multiply_elements((1, 5, 7, 8, 10)) == (5, 35, 56, 80)
