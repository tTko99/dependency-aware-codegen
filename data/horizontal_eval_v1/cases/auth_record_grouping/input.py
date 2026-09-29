

def solve(records):
    result = {}
    for record in records:
        result[record.get('kind')] = [record]
    return result
