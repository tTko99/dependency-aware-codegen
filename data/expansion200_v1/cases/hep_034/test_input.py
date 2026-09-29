import random
random.seed(42)
from solution import unique






def check(unique):
    assert unique([5, 3, 5, 2, 3, 3, 9, 0, 123]) == [0, 2, 3, 5, 9, 123]

check(unique)

def test_upstream_contract():
    random.seed(42)
    check(unique)
