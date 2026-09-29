

def solve(text):
    result = {}
    folded = text.casefold()
    for word in folded.split():
        result[word] = result.get(word, 0) + 1
    return result
