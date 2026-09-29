from collections import deque

def solve(values, k):
    queue = deque(values)
    return queue.rotate(k)
