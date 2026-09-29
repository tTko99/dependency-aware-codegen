import itertools

def solve(groups):
    return list(itertools.chain.from_iterable(groups))
