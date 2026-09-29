

def solve(value, lower, upper):
    if lower > upper:
        raise ValueError("reversed bounds")
    return max(lower, min(upper, value))
