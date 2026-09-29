import solution

def test_contract_0():
    assert solution.dict_depth({'a': 1, 'b': {'c': 'python'}}) == 2

def test_contract_1():
    assert solution.dict_depth({'a': 1, 'b': {'c': {'d': {}}}}) == 4
