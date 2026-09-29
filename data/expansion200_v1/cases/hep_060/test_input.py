import random
random.seed(42)
from solution import sum_to_n






def check(sum_to_n):
    assert sum_to_n(1) == 1
    assert sum_to_n(6) == 21
    assert sum_to_n(11) == 66
    assert sum_to_n(30) == 465
    assert sum_to_n(100) == 5050

check(sum_to_n)

def test_upstream_contract():
    random.seed(42)
    check(sum_to_n)
