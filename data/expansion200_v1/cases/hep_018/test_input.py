import random
random.seed(42)
from solution import how_many_times






def check(how_many_times):
    assert how_many_times('', 'x') == 0
    assert how_many_times('xyxyxyx', 'x') == 4
    assert how_many_times('cacacacac', 'cac') == 4
    assert how_many_times('john doe', 'john') == 1

check(how_many_times)

def test_upstream_contract():
    random.seed(42)
    check(how_many_times)
