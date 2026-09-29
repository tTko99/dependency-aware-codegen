# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import pascal

@pytest.mark.parametrize('input_data,expected', [([1], [[1]]), ([2], [[1], [1, 1]]), ([3], [[1], [1, 1], [1, 2, 1]]), ([4], [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1]]), ([5], [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1], [1, 4, 6, 4, 1]])])
def test_contract(input_data, expected):
    assert pascal(*input_data) == expected
