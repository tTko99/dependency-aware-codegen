import solution

def test_contract_0():
    assert solution.odd_values_string('abcdef') == 'ace'

def test_contract_1():
    assert solution.odd_values_string('lambs') == 'lms'
