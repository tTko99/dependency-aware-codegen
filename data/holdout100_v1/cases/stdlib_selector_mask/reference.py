import itertools

def solve(data, selectors):
    return list(itertools.compress(data, selectors))
