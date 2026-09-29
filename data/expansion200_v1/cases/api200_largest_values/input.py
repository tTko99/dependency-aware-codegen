import heapq

def solve(values, n):
    return heapq.nlargest(values, n)
