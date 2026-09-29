import pytest
from solution import solve

@pytest.mark.parametrize('args, expected', [(('2024-01-01', '2024-01-03'), 172800), (('2024-01-02', '2024-01-01'), -86400), (('2024-01-01T00:00:00', '2024-01-01T00:00:01.5'), 1.5)])
def test_contract(args, expected):
    assert solve(*args) == expected

