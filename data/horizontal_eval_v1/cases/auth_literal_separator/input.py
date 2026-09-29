import re

def solve(text, separator):
    return re.split(separator, text)
