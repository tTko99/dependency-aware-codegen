import solution

def test_contract_0():
    assert solution.add_nested_tuples(((2, 4), (5, 6), (3, 10), (2, 11)), ((7, 8), (4, 10), (2, 2), (8, 4))) == ((9, 12), (9, 16), (5, 12), (10, 15))
