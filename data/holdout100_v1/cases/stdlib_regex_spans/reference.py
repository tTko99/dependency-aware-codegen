import re

def solve(text):
    return [m.span() for m in re.finditer(r'\d+', text)]
