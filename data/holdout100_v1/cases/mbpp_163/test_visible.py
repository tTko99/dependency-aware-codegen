import solution
import math

def test_contract_0():
    assert math.isclose(solution.area_polygon(9, 7), 302.909, rel_tol=0.001)
