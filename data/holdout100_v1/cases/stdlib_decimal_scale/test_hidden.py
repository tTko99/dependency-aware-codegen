import solution

def test_contract_0():
    assert solution.solve('2.5', 0) == '2.5'

def test_contract_1():
    assert solution.solve('-3.2', 1) == '-32'

def test_contract_2():
    assert solution.solve('0.01', 2) == '1'
