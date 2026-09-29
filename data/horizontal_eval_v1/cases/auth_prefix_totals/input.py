import itertools

def solve(values):
    return list(itertools.cumulative_sum(values))
