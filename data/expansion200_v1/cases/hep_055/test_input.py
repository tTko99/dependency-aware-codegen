import random
random.seed(42)
from solution import fib






def check(fib):
    assert fib(10) == 55
    assert fib(1) == 1
    assert fib(8) == 21
    assert fib(11) == 89
    assert fib(12) == 144

check(fib)

def test_upstream_contract():
    random.seed(42)
    check(fib)
