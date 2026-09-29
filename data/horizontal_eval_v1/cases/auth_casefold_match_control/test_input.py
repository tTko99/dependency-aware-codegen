import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('Straße', 'STRASSE'), True), (('Σ', 'ς'), True), (('a ', 'a'), False), (('Hello', 'hello'), True)])
def test_contract(args, expected):
    assert solve(*args) == expected

