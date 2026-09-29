import solution

def test_contract_0():
    assert solution.solve(2 + 0j) == (2.0, 0.0)

def test_contract_1():
    assert solution.solve(-1 + 0j) == (1.0, 3.141592653589793)

def test_contract_2():
    assert solution.solve(2j) == (2.0, 1.5707963267948966)
