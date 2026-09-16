from solution import mean
def test_mean():
    assert mean([1, 2]) == 1.5
    assert mean([]) == 0
    assert mean([-3, -1]) == -2
