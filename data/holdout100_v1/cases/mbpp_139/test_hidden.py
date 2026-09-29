import solution
import math

def test_contract_0():
    assert math.isclose(solution.circle_circumference(10), 62.830000000000005, rel_tol=0.001)

def test_contract_1():
    assert math.isclose(solution.circle_circumference(4), 25.132, rel_tol=0.001)
