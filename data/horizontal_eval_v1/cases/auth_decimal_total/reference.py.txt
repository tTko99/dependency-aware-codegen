from decimal import Decimal

def solve(values):
    return format(sum((Decimal(x) for x in values), Decimal(0)), "f")
