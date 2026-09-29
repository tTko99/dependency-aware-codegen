from functools import reduce
from operator import add

def solve(values):
    return reduce(add, values)
