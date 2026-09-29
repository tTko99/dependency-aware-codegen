import datetime

def solve(year, week, day):
    return datetime.date(year,week,day).isoformat()
