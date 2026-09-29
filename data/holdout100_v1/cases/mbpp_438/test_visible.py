import solution

def test_contract_0():
    assert solution.count_bidirectional([(5, 6), (1, 3), (6, 5), (9, 1), (6, 5), (2, 1)]) == 2
