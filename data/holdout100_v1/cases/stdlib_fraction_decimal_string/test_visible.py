import solution

def test_contract_0():
    assert solution.solve('0.1') == (1, 10)

def test_contract_1():
    assert solution.solve('1.25') == (5, 4)
