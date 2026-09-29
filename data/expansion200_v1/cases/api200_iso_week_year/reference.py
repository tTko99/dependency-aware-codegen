from datetime import date

def solve(year, month, day):
    d = date(year, month, day)
    iso = d.isocalendar()
    return iso.year, iso.week, iso.weekday
