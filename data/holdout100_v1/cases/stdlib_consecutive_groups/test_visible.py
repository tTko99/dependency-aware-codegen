import solution

def test_contract_0():
    assert solution.solve([1, 1, 2, 1]) == [(1, 2), (2, 1), (1, 1)]

def test_contract_1():
    assert solution.solve(['b', 'a', 'a']) == [('b', 1), ('a', 2)]
