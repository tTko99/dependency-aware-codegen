

def solve(values):
    count = total = 0
    for value in values:
        count += 1
        total += value
    return count, total
