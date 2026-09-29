import solution

def test_contract_0():
    assert solution.maxAverageOfPath([[3, 4, 5], [8, 7, 6], [9, 5, 11]]) == 7.2

def test_contract_1():
    assert solution.maxAverageOfPath([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == 5.8
