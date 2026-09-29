from operator import itemgetter

def solve(values, indices):
    return itemgetter(*indices)(values)
