

def solve(rows):
    if rows and any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("ragged")
    return [list(column) for column in zip(*rows)]
