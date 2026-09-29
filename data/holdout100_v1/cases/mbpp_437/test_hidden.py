import solution

def test_contract_0():
    assert solution.remove_odd('python') == 'yhn'

def test_contract_1():
    assert solution.remove_odd('program') == 'rga'
