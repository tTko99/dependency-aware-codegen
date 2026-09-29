import random
random.seed(42)
from solution import count_distinct_characters






def check(count_distinct_characters):
    assert count_distinct_characters('') == 0
    assert count_distinct_characters('abcde') == 5
    assert count_distinct_characters('abcde' + 'cade' + 'CADE') == 5
    assert count_distinct_characters('aaaaAAAAaaaa') == 1
    assert count_distinct_characters('Jerry jERRY JeRRRY') == 5

check(count_distinct_characters)

def test_upstream_contract():
    random.seed(42)
    check(count_distinct_characters)
