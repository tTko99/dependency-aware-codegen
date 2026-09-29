import random
random.seed(42)
from solution import filter_by_prefix






def check(filter_by_prefix):
    assert filter_by_prefix([], 'john') == []
    assert filter_by_prefix(['xxx', 'asd', 'xxy', 'john doe', 'xxxAAA', 'xxx'], 'xxx') == ['xxx', 'xxxAAA', 'xxx']

check(filter_by_prefix)

def test_upstream_contract():
    random.seed(42)
    check(filter_by_prefix)
