import solution

def test_contract_0():
    assert solution.solve('true!') == (True, 4)

def test_contract_1():
    assert solution.solve('null') == (None, 4)

def test_contract_2():
    assert solution.solve('{} {}') == ({}, 2)
