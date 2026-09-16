from solution import intervals
def test_intervals():
    assert intervals([(4,5),(1,2),(2,3)]) == [(1,3),(4,5)]
    assert intervals([]) == []
    assert intervals([(1,5),(2,3)]) == [(1,5)]
