import json

def solve(text):
    return json.loads(text, object_pairs_hook=list)
