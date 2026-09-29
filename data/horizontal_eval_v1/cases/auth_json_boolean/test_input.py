import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('{"enabled":"false"}',), False), (('{"enabled":true}',), True), (('{}',), False), (('{"enabled":"TRUE"}',), True)])
def test_contract(args, expected):
    assert solve(*args) == expected

