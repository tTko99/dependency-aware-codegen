from itertools import tee, repeat
from operator import itemgetter
_marker = object()
UnequalIterablesError = ValueError
def _zip_equal(*iterables):
    return zip(*iterables, strict=True)

def zip_broadcast(*objects, scalar_types=(str, bytes), strict=False):
    if not objects:
        return

    iterables = []
    all_scalar = True
    for obj in objects:
        # If the object is one of our scalar types, turn it into an iterable
        # by wrapping it with itertools.repeat
        if scalar_types and isinstance(obj, scalar_types):
            iterables.append((repeat(obj), False))
        # Otherwise, test to see whether the object is iterable.
        # If it is, collect it. If it's not, treat it as a scalar.
        else:
            try:
                iterables.append((iter(obj), True))
            except TypeError:
                iterables.append((repeat(obj), False))
            else:
                all_scalar = False

    # If all the objects were scalar, we just emit them as a tuple.
    # Otherwise we zip the collected iterable objects.
    if all_scalar:
        yield tuple(objects)
    else:
        yield from zip(*(it for it, is_it in iterables))

        # For strict mode, we ensure that all the iterable objects have been
        # exhausted.
        if strict:
            for it, is_it in filter(itemgetter(1), iterables):
                if next(it, _marker) is not _marker:
                    raise UnequalIterablesError


def solve(objects, strict):
    return list(zip_broadcast(*objects, strict=strict))
