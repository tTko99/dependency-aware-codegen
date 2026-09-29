import random
random.seed(42)
from solution import intersperse






def check(intersperse):
    assert intersperse([], 7) == []
    assert intersperse([5, 6, 3, 2], 8) == [5, 8, 6, 8, 3, 8, 2]
    assert intersperse([2, 2, 2], 2) == [2, 2, 2, 2, 2]

check(intersperse)

def test_upstream_contract():
    random.seed(42)
    check(intersperse)
