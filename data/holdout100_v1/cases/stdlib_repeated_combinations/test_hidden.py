import solution

def test_contract_0():
    assert solution.solve(['a', 'b'], 2) == [('a', 'a'), ('a', 'b'), ('b', 'b')]

def test_contract_1():
    assert solution.solve([], 0) == [()]

def test_contract_2():
    assert solution.solve([], 2) == []
