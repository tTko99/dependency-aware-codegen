from fractions import Fraction

def solve(a, b):
    value = Fraction(a, b)
    return value.numerator, value.denominator
