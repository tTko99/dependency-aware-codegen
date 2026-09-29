import json

def solve(text):
    return bool(json.loads(text).get('enabled', False))
