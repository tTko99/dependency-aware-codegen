import json
def names(raw):
    return list(json.loads(raw, strict_mode=True))
