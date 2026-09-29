import pathlib

def solve(text):
    return pathlib.PurePosixPath(text).suffixes
