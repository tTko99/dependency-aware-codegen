

def solve(records):
    result = {}
    for record in records:
        group = result.setdefault(record.get('kind'), [])
        group.append(record)
    return result
