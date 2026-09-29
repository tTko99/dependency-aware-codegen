import solution

def test_contract_0():
    assert solution.check_element([1, 2, 3, 4], 7) == False

def test_contract_1():
    assert solution.check_element(['green', 'green', 'green', 'green'], 'green') == True
