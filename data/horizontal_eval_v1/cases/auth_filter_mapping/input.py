

def solve(mapping):
    for key in mapping:
        if mapping[key] is None:
            del mapping[key]
    return mapping
