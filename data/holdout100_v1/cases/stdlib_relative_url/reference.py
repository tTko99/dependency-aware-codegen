import urllib.parse

def solve(base, target):
    return urllib.parse.urljoin(base, target)
