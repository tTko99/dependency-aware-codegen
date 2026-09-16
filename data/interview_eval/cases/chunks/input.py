def chunks(xs, size):
    return [xs[i:i+size] for i in range(0, len(xs)-size+1, size)]
