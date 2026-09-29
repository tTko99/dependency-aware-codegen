import solution

def test_contract_0():
    assert solution.solve('archive.tar.gz') == ['.tar', '.gz']

def test_contract_1():
    assert solution.solve('a.txt') == ['.txt']
