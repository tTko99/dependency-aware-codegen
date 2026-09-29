from urllib.parse import urldefrag

def solve(url):
    return urldefrag(url).url
