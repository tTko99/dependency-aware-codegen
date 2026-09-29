from string import Template

def solve(text, mapping):
    template = Template(text)
    return template.safe_substitute(mapping)
