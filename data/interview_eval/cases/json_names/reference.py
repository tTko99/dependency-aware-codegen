import json
def names(raw):
    return [u['name'] for u in json.loads(raw).get('users', []) if 'name' in u]
