import itertools

def solve(values, threshold):
    return list(itertools.takewhile(lambda x: x < threshold, values))
