import solution

def test_contract_0():
    assert solution.recursive_list_sum([1, 2, [3, 4], [5, 6]]) == 21

def test_contract_1():
    assert solution.recursive_list_sum([10, 20, [30, 40], [50, 60]]) == 210
