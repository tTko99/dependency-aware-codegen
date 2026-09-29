from urllib.parse import parse_qs

def solve(query):
    return parse_qs(query, keep_blank_values=True)
