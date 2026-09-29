

def solve(records):
    result = {r['id']: r for r in records}
    return list(result.values())
