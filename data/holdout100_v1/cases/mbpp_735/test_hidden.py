import solution

def test_contract_0():
    assert solution.toggle_middle_bits(65) == 127

def test_contract_1():
    assert solution.toggle_middle_bits(11) == 13

def test_contract_2():
    assert solution.toggle_middle_bits(9) == 15
