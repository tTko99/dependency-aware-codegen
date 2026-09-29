

def solve(values, default):
    return next((x for x in values if x is not None), default)
