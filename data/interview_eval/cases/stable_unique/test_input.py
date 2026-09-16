from solution import unique
def test_unique():
    assert unique([3,1,3,2]) == [3,1,2]
    assert unique([[1],[2],[1]]) == [[1],[2]]
    assert unique([]) == []
