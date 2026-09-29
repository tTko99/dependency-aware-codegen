from datetime import datetime

def solve(start, end):
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return duration.total_seconds()
