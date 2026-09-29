import solution

def test_contract_0():
    assert solution.remove_odd([2, 4, 6]) == [2, 4, 6]

def test_contract_1():
    assert solution.remove_odd([10, 20, 3]) == [10, 20]
