import solution

def test_contract_0():
    assert solution.first_non_repeating_character('ababc') == 'c'

def test_contract_1():
    assert solution.first_non_repeating_character('abc') == 'a'
