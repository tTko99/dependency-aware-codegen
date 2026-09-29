import solution
import math

def test_contract_0():
    assert math.isclose(solution.area_polygon(10, 15), 1731.197, rel_tol=0.001)

def test_contract_1():
    assert math.isclose(solution.area_polygon(4, 20), 400.0, rel_tol=0.001)
