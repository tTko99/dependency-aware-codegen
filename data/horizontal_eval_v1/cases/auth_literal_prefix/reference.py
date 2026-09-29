

def solve(text, prefix):
    return text[len(prefix):] if prefix and text.startswith(prefix) else text
