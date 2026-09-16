from solution import median
def test_median():
    xs = [3,1,2,4]
    assert median(xs) == 2.5
    assert xs == [3,1,2,4]
    assert median([]) is None
    assert median([8,1,3]) == 3
