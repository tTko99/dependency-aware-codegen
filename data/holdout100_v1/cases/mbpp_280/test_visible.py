import solution

def test_contract_0():
    assert solution.sequential_search([11, 23, 58, 31, 56, 77, 43, 12, 65, 19], 31) == (True, 3)
