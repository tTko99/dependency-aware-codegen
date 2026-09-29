

def solve(value, default):
    try:
        return int(value)
    except TypeError:
        return default
