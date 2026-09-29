# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import find_first_in_sorted

@pytest.mark.parametrize('input_data,expected', [([[3, 4, 5, 5, 5, 5, 6], 5], 2), ([[3, 4, 5, 5, 5, 5, 6], 7], -1), ([[3, 4, 5, 5, 5, 5, 6], 2], -1), ([[3, 6, 7, 9, 9, 10, 14, 27], 14], 6), ([[0, 1, 6, 8, 13, 14, 67, 128], 80], -1), ([[0, 1, 6, 8, 13, 14, 67, 128], 67], 6), ([[0, 1, 6, 8, 13, 14, 67, 128], 128], 7)])
def test_contract(input_data, expected):
    assert find_first_in_sorted(*input_data) == expected
