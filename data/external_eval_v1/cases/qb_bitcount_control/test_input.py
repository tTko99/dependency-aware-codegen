# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import bitcount

@pytest.mark.parametrize('input_data,expected', [([127], 7), ([128], 1), ([3005], 9), ([13], 3), ([14], 3), ([27], 4), ([834], 4), ([254], 7), ([256], 1)])
def test_contract(input_data, expected):
    assert bitcount(*input_data) == expected
