from collections import Counter

def solve(values, k):
    return Counter(values).most_common(k)
