import solution

def test_contract_0():
    assert solution.subject_marks([('Physics', 96), ('Chemistry', 97), ('Biology', 45)]) == [('Biology', 45), ('Physics', 96), ('Chemistry', 97)]

def test_contract_1():
    assert solution.subject_marks([('Telugu', 49), ('Hindhi', 54), ('Social', 33)]) == [('Social', 33), ('Telugu', 49), ('Hindhi', 54)]
