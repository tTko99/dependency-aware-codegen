import solution

def test_contract_0():
    assert solution.solve(-8, -0.0) == -8

def test_contract_1():
    assert solution.solve(2, -1) == -2

def test_contract_2():
    assert solution.solve(-7, 0.0) == 7
