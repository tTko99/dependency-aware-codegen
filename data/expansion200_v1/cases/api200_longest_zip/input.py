import itertools

def solve(a, b, fill):
    return list(itertools.zip_longest(a, b, default=fill))
