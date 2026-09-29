import datetime

def solve(year, week, day):
    return datetime.date.fromisocalendar(year,week,day).isoformat()
