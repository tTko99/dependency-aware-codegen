import random
random.seed(42)
from solution import match_parens

def check(match_parens):

    # Check some simple cases
    assert match_parens(['()(', ')']) == 'Yes'
    assert match_parens([')', ')']) == 'No'
    assert match_parens(['(()(())', '())())']) == 'No'
    assert match_parens([')())', '(()()(']) == 'Yes'
    assert match_parens(['(())))', '(()())((']) == 'Yes'
    assert match_parens(['()', '())']) == 'No'
    assert match_parens(['(()(', '()))()']) == 'Yes'
    assert match_parens(['((((', '((())']) == 'No'
    assert match_parens([')(()', '(()(']) == 'No'
    assert match_parens([')(', ')(']) == 'No'
    

    # Check some edge cases that are easy to work out by hand.
    assert match_parens(['(', ')']) == 'Yes'
    assert match_parens([')', '(']) == 'Yes'

check(match_parens)

def test_upstream_contract():
    random.seed(42)
    check(match_parens)
