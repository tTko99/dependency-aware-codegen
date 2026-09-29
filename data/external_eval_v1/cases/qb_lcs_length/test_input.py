# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import lcs_length

@pytest.mark.parametrize('input_data,expected', [(['witch', 'sandwich'], 2), (['meow', 'homeowner'], 4), (['fun', ''], 0), (['fun', 'function'], 3), (['cyborg', 'cyber'], 3), (['physics', 'physics'], 7), (['space age', 'pace a'], 6), (['flippy', 'floppy'], 3), (['acbdegcedbg', 'begcfeubk'], 3)])
def test_contract(input_data, expected):
    assert lcs_length(*input_data) == expected
