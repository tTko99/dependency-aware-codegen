import re

def solve(text):
    return re.split(r"[,;]", text)
