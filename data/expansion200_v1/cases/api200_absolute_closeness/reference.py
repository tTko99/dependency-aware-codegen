import math

def solve(a, b, tolerance):
    return math.isclose(a, b, rel_tol=0, abs_tol=tolerance)
