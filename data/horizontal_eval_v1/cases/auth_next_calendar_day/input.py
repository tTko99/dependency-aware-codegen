from datetime import date, timedelta

def solve(text):
    value = date.fromisoformat(text)
    return date(value.year, value.month, value.day + 1).isoformat()
