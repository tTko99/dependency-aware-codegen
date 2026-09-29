from collections import Counter

def solve(left, right):
    counts = Counter(left)
    counts.subtract(right)
    return dict(counts)
