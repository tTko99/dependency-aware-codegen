from collections import deque

def solve(values, k):
    queue = deque(values)
    queue.rotate(k)
    return list(queue)
