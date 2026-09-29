

def solve(record, keys, default):
    for key in keys:
        record = record.get(key) or default
    return record
