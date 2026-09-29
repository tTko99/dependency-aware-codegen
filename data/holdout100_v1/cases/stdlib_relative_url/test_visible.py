import solution

def test_contract_0():
    assert solution.solve('https://a.org/p/', '../x') == 'https://a.org/x'

def test_contract_1():
    assert solution.solve('https://a.org/', 'https://b.org/y') == 'https://b.org/y'
