import solution

def test_contract_0():
    assert solution.solve('1.25', 2) == '125'

def test_contract_1():
    assert solution.solve('12', -1) == '1.2'
