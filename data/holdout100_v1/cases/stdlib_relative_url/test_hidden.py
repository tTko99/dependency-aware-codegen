import solution

def test_contract_0():
    assert solution.solve('https://a.org/p/index', 'z') == 'https://a.org/p/z'

def test_contract_1():
    assert solution.solve('https://a.org/p/', '/x?q=2') == 'https://a.org/x?q=2'

def test_contract_2():
    assert solution.solve('https://a.org/p', '') == 'https://a.org/p'
