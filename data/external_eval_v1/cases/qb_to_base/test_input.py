# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import to_base

@pytest.mark.parametrize('input_data,expected', [([8227, 18], '1771'), ([73, 8], '111'), ([16, 19], 'G'), ([31, 16], '1F'), ([41, 2], '101001'), ([44, 5], '134'), ([27, 23], '14'), ([56, 23], '2A'), ([8237, 24], 'E75'), ([8237, 34], '749')])
def test_contract(input_data, expected):
    assert to_base(*input_data) == expected
