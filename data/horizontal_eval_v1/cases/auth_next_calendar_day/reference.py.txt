from datetime import date, timedelta

def solve(text):
    following = date.fromisoformat(text) + timedelta(days=1)
    return following.isoformat()
