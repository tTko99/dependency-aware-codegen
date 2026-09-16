def chunks(xs, size):
    if size <= 0:
        raise ValueError('size')
    return [xs[i:i+size] for i in range(0, len(xs), size)]
