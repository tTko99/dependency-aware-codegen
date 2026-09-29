# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import sieve

@pytest.mark.parametrize('input_data,expected', [([1], []), ([2], [2]), ([4], [2, 3]), ([7], [2, 3, 5, 7]), ([20], [2, 3, 5, 7, 11, 13, 17, 19]), ([50], [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47])])
def test_contract(input_data, expected):
    assert sieve(*input_data) == expected
