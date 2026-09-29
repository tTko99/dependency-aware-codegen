import itertools

def solve(values, threshold):
    return list(itertools.dropwhile(lambda x: x < threshold, values))
