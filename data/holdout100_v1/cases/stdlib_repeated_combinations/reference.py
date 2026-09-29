import itertools

def solve(items, r):
    return list(itertools.combinations_with_replacement(items, r))
