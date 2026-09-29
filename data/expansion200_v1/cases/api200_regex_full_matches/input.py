import re

def solve(text):
    return re.findall(r"([A-Za-z]+)([0-9]+)", text)
