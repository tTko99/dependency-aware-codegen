import random
random.seed(42)
from solution import parse_nested_parens






def check(parse_nested_parens):
    assert parse_nested_parens('(()()) ((())) () ((())()())') == [2, 3, 1, 3]
    assert parse_nested_parens('() (()) ((())) (((())))') == [1, 2, 3, 4]
    assert parse_nested_parens('(()(())((())))') == [4]

check(parse_nested_parens)

def test_upstream_contract():
    random.seed(42)
    check(parse_nested_parens)
