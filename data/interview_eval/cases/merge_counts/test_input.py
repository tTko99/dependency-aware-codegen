from solution import merge
def test_merge():
    a = {'x':2}
    assert merge(a, {'x':3,'y':1}) == {'x':5,'y':1}
    assert a == {'x':2}
    assert merge({'x':-2}, {'x':1}) == {'x':-1}
