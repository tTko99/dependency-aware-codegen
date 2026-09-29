import json

def solve(text):
    decoder = json.JSONDecoder()
    return decoder.raw_decode(text)
