import random
random.seed(42)
from solution import largest_divisor






def check(largest_divisor):
    assert largest_divisor(3) == 1
    assert largest_divisor(7) == 1
    assert largest_divisor(10) == 5
    assert largest_divisor(100) == 50
    assert largest_divisor(49) == 7

check(largest_divisor)

def test_upstream_contract():
    random.seed(42)
    check(largest_divisor)
