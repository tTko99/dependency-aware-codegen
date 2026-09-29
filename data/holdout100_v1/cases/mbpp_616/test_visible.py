import solution

def test_contract_0():
    assert solution.tuple_modulo((12, 6, 7, 8), (7, 8, 9, 7)) == (5, 6, 7, 1)
