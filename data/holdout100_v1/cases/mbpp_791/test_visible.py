import solution

def test_contract_0():
    assert solution.remove_nested((3, 7, 9, (6, 8), 12)) == (3, 7, 9, 12)

def test_contract_1():
    assert solution.remove_nested((3, 7, 9, (6, 8), (5, 12), 12)) == (3, 7, 9, 12)
