import solution

def test_contract_0():
    assert solution.solve('') == []

def test_contract_1():
    assert solution.solve('abc') == []

def test_contract_2():
    assert solution.solve('9 00') == [(0, 1), (2, 4)]
