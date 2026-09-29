import solution

def test_contract_0():
    assert solution.solve(2021, 1, 1) == '2021-01-04'

def test_contract_1():
    assert solution.solve(2015, 53, 4) == '2015-12-31'

def test_contract_2():
    assert solution.solve(2024, 1, 1) == '2024-01-01'
