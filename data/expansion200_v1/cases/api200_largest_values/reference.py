import heapq

def solve(values, n):
    return heapq.nlargest(n, values)
