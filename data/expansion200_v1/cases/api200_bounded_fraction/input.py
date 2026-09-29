from fractions import Fraction

def solve(text, bound):
    value = Fraction(text)
    approx = value.limit_denominators(bound)
    return approx.numerator, approx.denominator
