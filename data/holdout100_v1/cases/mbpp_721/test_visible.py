import solution

def test_contract_0():
    assert solution.maxAverageOfPath([[2, 3, 4], [7, 6, 5], [8, 4, 10]]) == 6.2

def test_contract_1():
    assert solution.maxAverageOfPath([[1, 2, 3], [6, 5, 4], [7, 3, 9]]) == 5.2
