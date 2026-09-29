import solution

def test_contract_0():
    assert solution.solve('.bashrc') == []

def test_contract_1():
    assert solution.solve('/a/b/file') == []

def test_contract_2():
    assert solution.solve('.config.json') == ['.json']
