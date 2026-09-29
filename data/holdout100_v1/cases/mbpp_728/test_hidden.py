import solution

def test_contract_0():
    assert solution.sum_list([15, 20, 30], [15, 45, 75]) == [30, 65, 105]

def test_contract_1():
    assert solution.sum_list([1, 2, 3], [5, 6, 7]) == [6, 8, 10]
