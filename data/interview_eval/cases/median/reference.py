def median(xs):
    values = sorted(xs)
    n = len(values)
    if not n:
        return None
    return values[n//2] if n % 2 else (values[n//2-1] + values[n//2]) / 2
