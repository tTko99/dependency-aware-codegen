# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import next_palindrome

@pytest.mark.parametrize('input_data,expected', [([[1, 4, 9, 4, 1]], [1, 5, 0, 5, 1]), ([[1, 3, 1]], [1, 4, 1]), ([[4, 7, 2, 5, 5, 2, 7, 4]], [4, 7, 2, 6, 6, 2, 7, 4]), ([[4, 7, 2, 5, 2, 7, 4]], [4, 7, 2, 6, 2, 7, 4]), ([[9, 9, 9]], [1, 0, 0, 1])])
def test_contract(input_data, expected):
    assert next_palindrome(*input_data) == expected
