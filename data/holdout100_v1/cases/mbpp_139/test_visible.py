import solution
import math

def test_contract_0():
    assert math.isclose(solution.circle_circumference(5), 31.415000000000003, rel_tol=0.001)
