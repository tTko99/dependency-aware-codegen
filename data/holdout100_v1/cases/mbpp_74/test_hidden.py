import solution

def test_contract_0():
    assert solution.is_samepatterns(['red', 'green', 'green'], ['a', 'b', 'b']) == True

def test_contract_1():
    assert solution.is_samepatterns(['red', 'green', 'greenn'], ['a', 'b', 'b']) == False
