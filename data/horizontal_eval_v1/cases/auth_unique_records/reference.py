

def solve(records):
    result = {}
    for row in records:
        if row['id'] not in result:
            result[row['id']] = row
    return list(result.values())
