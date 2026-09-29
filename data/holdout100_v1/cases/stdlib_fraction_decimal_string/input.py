import fractions

def solve(text):
    value = fractions.Fraction(float(text))
    return (value.numerator,value.denominator)
