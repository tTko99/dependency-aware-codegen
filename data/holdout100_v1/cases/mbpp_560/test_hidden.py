import solution

def test_contract_0():
    assert solution.union_elements((3, 4, 5, 6), (5, 7, 4, 10)) == (3, 4, 5, 6, 7, 10)

def test_contract_1():
    assert solution.union_elements((1, 2, 3, 4), (3, 4, 5, 6)) == (1, 2, 3, 4, 5, 6)
