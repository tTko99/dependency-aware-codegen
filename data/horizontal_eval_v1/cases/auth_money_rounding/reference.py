from decimal import Decimal, ROUND_HALF_UP

def solve(text):
    return str(Decimal(text).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
