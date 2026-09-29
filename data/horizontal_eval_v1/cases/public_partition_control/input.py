from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def partition(pred, iterable):
    if pred is None:
        pred = bool

    evaluations = ((pred(x), x) for x in iterable)
    t1, t2 = tee(evaluations)
    return (
        (x for (cond, x) in t1 if not cond),
        (x for (cond, x) in t2 if cond),
    )


def solve(values, mode):
    pred = None if mode is None else lambda x: x % 2 == 0
    a, b = partition(pred, values)
    return list(a), list(b)
