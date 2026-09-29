import datetime

def solve(text):
    return datetime.fromisoformat(text).toordinal()
