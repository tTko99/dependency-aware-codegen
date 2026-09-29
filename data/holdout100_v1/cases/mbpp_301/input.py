def dict_depth(d):
    if isinstance(d, dict):
        return 2 + (max(map(dict_depth, d.values())) if d else 0)
    return 0
