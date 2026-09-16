from solution import flatten
def test_flatten():
    assert flatten([[1],[2,3]]) == [1,2,3]
    assert flatten([1,[2,[3]],'ab',[]]) == [1,2,3,'ab']
