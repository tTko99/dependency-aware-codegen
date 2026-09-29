# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import kheapsort

@pytest.mark.parametrize('input_data,expected', [([[1, 2, 3, 4, 5], 0], [1, 2, 3, 4, 5]), ([[3, 2, 1, 5, 4], 2], [1, 2, 3, 4, 5]), ([[5, 4, 3, 2, 1], 4], [1, 2, 3, 4, 5]), ([[3, 12, 5, 1, 6], 3], [1, 3, 5, 6, 12])])
def test_contract(input_data, expected):
    assert list(kheapsort(*input_data)) == expected
