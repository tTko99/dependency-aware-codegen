import solution

def test_contract_0():
    assert solution.count_Pairs([1, 1, 1, 1], 4) == 0

def test_contract_1():
    assert solution.count_Pairs([1, 2, 1], 3) == 2
