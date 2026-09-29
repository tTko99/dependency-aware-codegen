import json

def solve(text):
    record = json.loads(text)
    return list(record.items())
