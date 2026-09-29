import solution

def test_contract_0():
    assert solution.solve(1j) == (1.0, 1.5707963267948966)

def test_contract_1():
    assert solution.solve(0 + 0j) == (0.0, 0.0)
