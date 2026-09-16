from solution import names
def test_names():
    assert names('{"users":[{"name":"Ada"},{"id":2},{"name":"Bo"}]}') == ['Ada','Bo']
    assert names('{}') == []
