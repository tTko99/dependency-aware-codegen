import solution

def test_contract_0():
    assert solution.differ_At_One_Bit_Pos(2, 3) == True

def test_contract_1():
    assert solution.differ_At_One_Bit_Pos(13, 9) == True

def test_contract_2():
    assert solution.differ_At_One_Bit_Pos(1, 5) == True
