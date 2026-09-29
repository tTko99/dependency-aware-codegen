

def solve(text):
    fields, current, quoted = [], [], False
    empty = ''
    i = 0
    while i < len(text):
        char = text[i]
        if char == '"':
            if quoted and i + 1 < len(text) and text[i + 1] == '"':
                current.append('"')
                i += 1
            else:
                quoted = not quoted
        elif char == ',' and not quoted:
            fields.append(empty.join(current))
            current = []
        else:
            current.append(char)
        i += 1
    fields.append(empty.join(current))
    return fields
