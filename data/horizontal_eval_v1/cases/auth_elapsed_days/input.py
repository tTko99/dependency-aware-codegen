from datetime import datetime

def solve(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds
