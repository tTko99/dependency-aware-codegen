import solution

def test_contract_0():
    assert solution.differ_At_One_Bit_Pos(15, 8) == False

def test_contract_1():
    assert solution.differ_At_One_Bit_Pos(2, 4) == False

def test_contract_2():
    assert solution.differ_At_One_Bit_Pos(5, 1) == True
