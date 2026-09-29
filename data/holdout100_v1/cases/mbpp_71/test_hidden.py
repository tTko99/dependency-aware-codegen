import solution

def test_contract_0():
    assert solution.comb_sort([41, 32, 15, 19, 22]) == [15, 19, 22, 32, 41]

def test_contract_1():
    assert solution.comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]
