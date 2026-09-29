import solution

def test_contract_0():
    assert solution.solve(2020, 1, 1) == '2019-12-30'

def test_contract_1():
    assert solution.solve(2020, 53, 7) == '2021-01-03'
