import re

def solve(text):
    return re.findall(r'\d+', text)
