def intervals(xs):
    return [(min(a for a,b in xs), max(b for a,b in xs))]
