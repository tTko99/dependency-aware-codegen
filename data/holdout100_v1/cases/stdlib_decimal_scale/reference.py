import decimal

def solve(text,n):
    return str(decimal.Decimal(text).scaleb(n))
