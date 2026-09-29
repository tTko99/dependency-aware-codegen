from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def partition(pred, iterable):
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
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
