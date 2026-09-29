import solution

def test_contract_0():
    assert solution.reverse_string_list(['Red', 'Green', 'Blue', 'White', 'Black']) == ['deR', 'neerG', 'eulB', 'etihW', 'kcalB']

def test_contract_1():
    assert solution.reverse_string_list(['jack', 'john', 'mary']) == ['kcaj', 'nhoj', 'yram']
