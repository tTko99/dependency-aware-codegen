import solution

def test_contract_0():
    assert solution.solve([(2, 3), (3, 2)]) == [8, 9]

def test_contract_1():
    assert solution.solve([(5, 0)]) == [1]
