import solution

def test_contract_0():
    assert solution.wind_chill(10, 8) == 6

def test_contract_1():
    assert solution.wind_chill(40, 20) == 19
