import random
random.seed(42)
from solution import flip_case






def check(flip_case):
    assert flip_case('') == ''
    assert flip_case('Hello!') == 'hELLO!'
    assert flip_case('These violent delights have violent ends') == 'tHESE VIOLENT DELIGHTS HAVE VIOLENT ENDS'

check(flip_case)

def test_upstream_contract():
    random.seed(42)
    check(flip_case)
