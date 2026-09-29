import bisect

def solve(values, target):
    return bisect.bisect_right(values, target)
