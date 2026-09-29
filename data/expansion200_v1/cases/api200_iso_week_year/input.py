from datetime import date

def solve(year, month, day):
    d = date(year, month, day)
    iso = d.isocalendar()
    return year, iso.week, d.weekday()
