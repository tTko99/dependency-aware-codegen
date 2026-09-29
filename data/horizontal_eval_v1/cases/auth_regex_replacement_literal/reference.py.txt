import re

def solve(text, pattern, replacement):
    return re.sub(pattern, lambda match: replacement, text)
