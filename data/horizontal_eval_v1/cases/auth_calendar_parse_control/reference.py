import datetime

def solve(text):
    return datetime.date.fromisoformat(text).toordinal()
