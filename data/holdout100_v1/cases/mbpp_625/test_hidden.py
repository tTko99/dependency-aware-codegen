import solution

def test_contract_0():
    assert solution.swap_List([1, 2, 3]) == [3, 2, 1]

def test_contract_1():
    assert solution.swap_List([4, 5, 6]) == [6, 5, 4]
