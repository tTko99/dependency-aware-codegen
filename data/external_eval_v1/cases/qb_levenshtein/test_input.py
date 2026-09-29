# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import levenshtein

@pytest.mark.parametrize('input_data,expected', [(['electron', 'neutron'], 3), (['kitten', 'sitting'], 3), (['rosettacode', 'raisethysword'], 8), (['abcdefg', 'gabcdef'], 2), (['', ''], 0), (['hello', 'olleh'], 4)])
def test_contract(input_data, expected):
    assert levenshtein(*input_data) == expected
