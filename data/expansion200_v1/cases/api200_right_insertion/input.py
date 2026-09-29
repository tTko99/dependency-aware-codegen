import bisect

def solve(values, target):
    return bisect.bisect_left(values, target)
