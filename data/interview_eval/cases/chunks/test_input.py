from solution import chunks
def test_chunks():
    assert chunks([1,2,3,4,5], 2) == [[1,2],[3,4],[5]]
    assert chunks([], 2) == []
    try:
        chunks([1], -1)
    except ValueError:
        return
    assert False, 'negative size must raise'
