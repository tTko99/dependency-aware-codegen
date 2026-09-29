import solution

def test_contract_0():
    assert solution.solve('123 tail') == (123, 3)

def test_contract_1():
    assert solution.solve('[1,2]x') == ([1, 2], 5)
