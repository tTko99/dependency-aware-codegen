import solution

def test_contract_0():
    assert solution.sequential_search([9, 10, 17, 19, 22, 39, 48, 56], 48) == (True, 6)

def test_contract_1():
    assert solution.sequential_search([12, 32, 45, 62, 35, 47, 44, 61], 61) == (True, 7)
