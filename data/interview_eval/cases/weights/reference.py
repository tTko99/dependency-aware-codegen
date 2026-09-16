def weights(xs):
    if any(x < 0 for x in xs):
        raise ValueError('negative')
    total = sum(xs)
    return [x / total if total else 0 for x in xs]
