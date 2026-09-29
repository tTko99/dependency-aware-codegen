import solution

def test_contract_0():
    assert solution.return_sum({'a': 25, 'b': 18, 'c': 45}) == 88

def test_contract_1():
    assert solution.return_sum({'a': 100, 'b': 200, 'c': 300}) == 600
