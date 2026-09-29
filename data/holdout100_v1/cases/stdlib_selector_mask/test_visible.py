import solution

def test_contract_0():
    assert solution.solve(['a', 'b', 'c'], [1, 0, 1]) == ['a', 'c']

def test_contract_1():
    assert solution.solve([0, 2], [1, 0]) == [0]
