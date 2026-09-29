import solution

def test_contract_0():
    assert solution.check_expression('{()}[{]') == False

def test_contract_1():
    assert solution.check_expression('{()}[{}]') == True
