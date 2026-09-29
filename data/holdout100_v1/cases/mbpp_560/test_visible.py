import solution

def test_contract_0():
    assert solution.union_elements((11, 12, 13, 14), (13, 15, 16, 17)) == (11, 12, 13, 14, 15, 16, 17)
