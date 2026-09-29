import solution
import math

def test_contract_0():
    assert math.isclose(solution.surfacearea_sphere(10), 1256.6370614359173, rel_tol=0.001)

def test_contract_1():
    assert math.isclose(solution.surfacearea_sphere(20), 5026.548245743669, rel_tol=0.001)
