import solution

def test_contract_0():
    assert solution.solve('-0.3') == (-3, 10)

def test_contract_1():
    assert solution.solve('0') == (0, 1)

def test_contract_2():
    assert solution.solve('2.50') == (5, 2)
