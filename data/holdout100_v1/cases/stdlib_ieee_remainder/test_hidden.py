import solution

def test_contract_0():
    assert solution.solve(-7, 4) == 1

def test_contract_1():
    assert solution.solve(5, 3) == -1

def test_contract_2():
    assert solution.solve(3, -2) == -1
