from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def zip_broadcast(*objects, scalar_types=(str, bytes), strict=False):

    def is_scalar(obj):
        if scalar_types and isinstance(obj, scalar_types):
            return True
        try:
            iter(obj)
        except TypeError:
            return True
        else:
            return False

    size = len(objects)
    if not size:
        return

    iterables, iterable_positions = [], []
    scalars, scalar_positions = [], []
    for i, obj in enumerate(objects):
        if is_scalar(obj):
            scalars.append(obj)
            scalar_positions.append(i)
        else:
            iterables.append(iter(obj))
            iterable_positions.append(i)

    if len(scalars) == size:
        yield tuple(objects)
        return

    zipper = _zip_equal if strict else zip
    for item in zipper(*iterables):
        new_item = [None] * size

        for i, elem in zip(iterable_positions, item):
            new_item[i] = elem

        for i, elem in zip(scalar_positions, scalars):
            new_item[i] = elem

        yield tuple(new_item)


def solve(objects, strict):
    return list(zip_broadcast(*objects, strict=strict))
