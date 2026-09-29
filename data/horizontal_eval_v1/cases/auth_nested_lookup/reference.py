

def solve(record, keys, default):
    for key in keys:
        if not isinstance(record, dict) or key not in record:
            return default
        record = record[key]
    return record
