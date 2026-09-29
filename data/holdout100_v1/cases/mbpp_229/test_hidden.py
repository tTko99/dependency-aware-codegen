import solution

def test_contract_0():
    assert solution.re_arrange_array([10, 24, 36, -42, -39, -78, 85], 7) == [-42, -39, -78, 10, 24, 36, 85]

def test_contract_1():
    assert solution.re_arrange_array([12, -14, -26, 13, 15], 5) == [-14, -26, 12, 13, 15]
