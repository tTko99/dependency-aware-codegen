

def solve(records):
    return sorted(records, key=lambda row: float(row['score']))
