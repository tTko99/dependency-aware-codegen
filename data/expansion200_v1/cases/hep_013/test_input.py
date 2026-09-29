import random
random.seed(42)
from solution import greatest_common_divisor






def check(greatest_common_divisor):
    assert greatest_common_divisor(3, 7) == 1
    assert greatest_common_divisor(10, 15) == 5
    assert greatest_common_divisor(49, 14) == 7
    assert greatest_common_divisor(144, 60) == 12

check(greatest_common_divisor)

def test_upstream_contract():
    random.seed(42)
    check(greatest_common_divisor)
