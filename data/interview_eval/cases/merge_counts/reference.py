def merge(a, b):
    result = dict(a)
    for key, value in b.items():
        result[key] = result.get(key, 0) + value
    return result
