import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(({'x': '中文'},), '{"x": "中文"}'), (({'b': 2, 'a': 1},), '{"a": 1, "b": 2}'), (({},), '{}'), (({'x': 'é'},), '{"x": "é"}')])
def test_contract(args, expected):
    assert solve(*args) == expected

