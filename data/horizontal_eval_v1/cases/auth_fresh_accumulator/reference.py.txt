

def solve(value, bucket=None):
    return ([] if bucket is None else list(bucket)) + [value]
