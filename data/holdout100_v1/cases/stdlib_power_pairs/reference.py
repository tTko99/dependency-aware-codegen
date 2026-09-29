import itertools

def solve(pairs):
    return list(itertools.starmap(pow, pairs))
