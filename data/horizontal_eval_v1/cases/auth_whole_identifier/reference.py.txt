import re

def solve(text):
    return re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', text) is not None
