import random
random.seed(42)
from solution import make_palindrome






def check(make_palindrome):
    assert make_palindrome('') == ''
    assert make_palindrome('x') == 'x'
    assert make_palindrome('xyz') == 'xyzyx'
    assert make_palindrome('xyx') == 'xyx'
    assert make_palindrome('jerry') == 'jerryrrej'

check(make_palindrome)

def test_upstream_contract():
    random.seed(42)
    check(make_palindrome)
