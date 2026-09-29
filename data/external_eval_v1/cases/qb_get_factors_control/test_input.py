# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import get_factors

@pytest.mark.parametrize('input_data,expected', [([1], []), ([100], [2, 2, 5, 5]), ([101], [101]), ([104], [2, 2, 2, 13]), ([2], [2]), ([3], [3]), ([17], [17]), ([63], [3, 3, 7]), ([74], [2, 37]), ([73], [73]), ([9837], [3, 3, 1093])])
def test_contract(input_data, expected):
    assert get_factors(*input_data) == expected
