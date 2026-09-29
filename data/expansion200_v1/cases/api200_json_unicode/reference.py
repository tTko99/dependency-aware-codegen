import json

def solve(record):
    return json.dumps(record, sort_keys=True, ensure_ascii=False)
