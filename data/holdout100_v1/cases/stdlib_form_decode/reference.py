import urllib.parse

def solve(text):
    return urllib.parse.unquote_plus(text)
