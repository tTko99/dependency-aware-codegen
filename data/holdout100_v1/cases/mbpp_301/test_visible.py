import solution

def test_contract_0():
    assert solution.dict_depth({1: 'Sun', 2: {3: {4: 'Mon'}}}) == 3
