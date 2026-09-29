# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import flatten

@pytest.mark.parametrize('input_data,expected', [([[[1, [], [2, 3]], [[4]], 5]], [1, 2, 3, 4, 5]), ([[[], [], [], [], []]], []), ([[[], [], 1, [], 1, [], []]], [1, 1]), ([[1, 2, 3, [[4]]]], [1, 2, 3, 4]), ([[1, 4, 6]], [1, 4, 6]), ([['moe', 'curly', 'larry']], ['moe', 'curly', 'larry']), ([['a', 'b', ['c'], ['d'], [['e']]]], ['a', 'b', 'c', 'd', 'e'])])
def test_contract(input_data, expected):
    assert list(flatten(*input_data)) == expected
