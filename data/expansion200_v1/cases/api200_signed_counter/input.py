from collections import Counter

def solve(left, right):
    return dict(Counter(left) - Counter(right))
