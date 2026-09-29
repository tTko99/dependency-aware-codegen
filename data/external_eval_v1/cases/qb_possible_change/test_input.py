# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import possible_change

@pytest.mark.parametrize('input_data,expected', [([[1, 4, 2], -7], 0), ([[1, 5, 10, 25], 11], 4), ([[1, 5, 10, 25], 75], 121), ([[1, 5, 10, 25], 34], 18), ([[1, 5, 10], 34], 16), ([[1, 5, 10, 25], 140], 568), ([[1, 5, 10, 25, 50], 140], 786), ([[1, 5, 10, 25, 50, 100], 140], 817), ([[1, 3, 7, 42, 78], 140], 981), ([[3, 7, 42, 78], 140], 20)])
def test_contract(input_data, expected):
    assert possible_change(*input_data) == expected
