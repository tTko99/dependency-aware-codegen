import solution

def test_contract_0():
    assert solution.solve(0.125) == (0.5, -2)

def test_contract_1():
    assert solution.solve(0) == (0.0, 0)

def test_contract_2():
    assert solution.solve(12) == (0.75, 4)
