import json

def solve(text):
    value = json.loads(text).get('enabled', False)
    return value.lower() == 'true' if isinstance(value, str) else bool(value)
