# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import next_permutation

@pytest.mark.parametrize('input_data,expected', [([[3, 2, 4, 1]], [3, 4, 1, 2]), ([[3, 5, 6, 2, 1]], [3, 6, 1, 2, 5]), ([[3, 5, 6, 2]], [3, 6, 2, 5]), ([[4, 5, 1, 7, 9]], [4, 5, 1, 9, 7]), ([[4, 5, 8, 7, 1]], [4, 7, 1, 5, 8]), ([[9, 5, 2, 6, 1]], [9, 5, 6, 1, 2]), ([[44, 5, 1, 7, 9]], [44, 5, 1, 9, 7]), ([[3, 4, 5]], [3, 5, 4])])
def test_contract(input_data, expected):
    assert next_permutation(*input_data) == expected
