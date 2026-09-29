from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def split_after(iterable, pred, maxsplit=-1):
    if maxsplit == 0:
        yield list(iterable)
        return

    buf = []
    it = iter(iterable)
    for item in it:
        buf.append(item)
        if pred(item) and buf:
            yield buf
            if maxsplit == 1:
                buf = list(it)
                if buf:
                    yield buf
                return
            buf = []
            maxsplit -= 1
    if buf:
        yield buf


def solve(values, maxsplit):
    return list(split_after(values, lambda x: x == 0, maxsplit=maxsplit))
