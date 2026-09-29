import solution

def test_contract_0():
    assert solution.pos_count([1, 2, 3, 4]) == 4

def test_contract_1():
    assert solution.pos_count([1, -2, 3, -4]) == 2
