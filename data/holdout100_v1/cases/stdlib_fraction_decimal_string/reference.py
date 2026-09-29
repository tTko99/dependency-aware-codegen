import fractions

def solve(text):
    value = fractions.Fraction(text)
    return (value.numerator,value.denominator)
