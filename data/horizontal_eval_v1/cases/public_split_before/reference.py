from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def split_before(iterable, pred, maxsplit=-1):
    if maxsplit == 0:
        yield list(iterable)
        return

    buf = []
    it = iter(iterable)
    for item in it:
        if pred(item) and buf:
            yield buf
            if maxsplit == 1:
                yield [item] + list(it)
                return
            buf = []
            maxsplit -= 1
        buf.append(item)
    if buf:
        yield buf


def solve(values, maxsplit):
    return list(split_before(values, lambda x: x < 0, maxsplit=maxsplit))
