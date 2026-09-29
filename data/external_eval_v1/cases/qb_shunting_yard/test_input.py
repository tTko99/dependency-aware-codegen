# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import shunting_yard

@pytest.mark.parametrize('input_data,expected', [([[]], []), ([[30]], [30]), ([[10, '-', 5, '-', 2]], [10, 5, '-', 2, '-']), ([[34, '-', 12, '/', 5]], [34, 12, 5, '/', '-']), ([[4, '+', 9, '*', 9, '-', 10, '+', 13]], [4, 9, 9, '*', '+', 10, '-', 13, '+']), ([[7, '*', 43, '-', 7, '+', 13, '/', 7]], [7, 43, '*', 7, '-', 13, 7, '/', '+'])])
def test_contract(input_data, expected):
    assert shunting_yard(*input_data) == expected
