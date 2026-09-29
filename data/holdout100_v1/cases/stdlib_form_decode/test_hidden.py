import solution

def test_contract_0():
    assert solution.solve('++') == '  '

def test_contract_1():
    assert solution.solve('%E4%B8%AD+ok') == '中 ok'

def test_contract_2():
    assert solution.solve('') == ''
