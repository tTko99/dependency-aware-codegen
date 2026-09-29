import solution
import math

def test_contract_0():
    assert math.isclose(solution.surfacearea_sphere(15), 2827.4333882308138, rel_tol=0.001)
