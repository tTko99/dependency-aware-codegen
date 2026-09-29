import solution

def test_contract_0():
    assert solution.multiply_elements((12, 13, 14, 9, 15)) == (156, 182, 126, 135)

def test_contract_1():
    assert solution.multiply_elements((12,)) == ()
