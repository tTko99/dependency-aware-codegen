from solution import weights
def test_weights():
    assert weights([1,3]) == [0.25,0.75]
    assert weights([0,0]) == [0,0]
    assert weights([]) == []
    try:
        weights([-1,2])
    except ValueError:
        return
    assert False
