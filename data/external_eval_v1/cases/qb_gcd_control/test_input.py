# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import gcd

@pytest.mark.parametrize('input_data,expected', [([17, 0], 17), ([13, 13], 13), ([37, 600], 1), ([20, 100], 20), ([624129, 2061517], 18913), ([3, 12], 3)])
def test_contract(input_data, expected):
    assert gcd(*input_data) == expected
