import textwrap

def solve(text, width):
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
