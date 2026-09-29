import solution

def test_contract_0():
    assert solution.solve('a12b3') == [(1, 3), (4, 5)]

def test_contract_1():
    assert solution.solve('123') == [(0, 3)]
