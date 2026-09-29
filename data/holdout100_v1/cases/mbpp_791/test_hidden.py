import solution

def test_contract_0():
    assert solution.remove_nested((2, 6, 8, (5, 7), 11)) == (2, 6, 8, 11)

def test_contract_1():
    assert solution.remove_nested((1, 5, 7, (4, 6), 10)) == (1, 5, 7, 10)
