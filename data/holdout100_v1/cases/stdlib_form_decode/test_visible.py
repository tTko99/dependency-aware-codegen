import solution

def test_contract_0():
    assert solution.solve('a+b') == 'a b'

def test_contract_1():
    assert solution.solve('%2B+x') == '+ x'
