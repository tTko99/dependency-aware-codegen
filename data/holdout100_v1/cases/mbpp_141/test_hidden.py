import solution

def test_contract_0():
    assert solution.pancake_sort([98, 12, 54, 36, 85]) == [12, 36, 54, 85, 98]

def test_contract_1():
    assert solution.pancake_sort([41, 42, 32, 12, 23]) == [12, 23, 32, 41, 42]
