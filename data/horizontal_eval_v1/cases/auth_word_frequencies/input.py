

def solve(text):
    result = {}
    lowered = text.lower()
    for word in lowered.split(' '):
        result[word] = result.get(word, 0) + 1
    return result
