import random
random.seed(42)
from solution import longest






def check(longest):
    assert longest([]) == None
    assert longest(['x', 'y', 'z']) == 'x'
    assert longest(['x', 'yyy', 'zzzz', 'www', 'kkkk', 'abc']) == 'zzzz'

check(longest)

def test_upstream_contract():
    random.seed(42)
    check(longest)
