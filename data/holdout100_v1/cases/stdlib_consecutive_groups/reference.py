import itertools

def solve(values):
    return [(k, len(list(g))) for k,g in itertools.groupby(values)]
