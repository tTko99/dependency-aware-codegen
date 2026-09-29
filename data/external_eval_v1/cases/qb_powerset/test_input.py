# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import powerset

@pytest.mark.parametrize('input_data,expected', [([['a', 'b', 'c']], [[], ['c'], ['b'], ['b', 'c'], ['a'], ['a', 'c'], ['a', 'b'], ['a', 'b', 'c']]), ([['a', 'b']], [[], ['b'], ['a'], ['a', 'b']]), ([['a']], [[], ['a']]), ([[]], [[]]), ([['x', 'df', 'z', 'm']], [[], ['m'], ['z'], ['z', 'm'], ['df'], ['df', 'm'], ['df', 'z'], ['df', 'z', 'm'], ['x'], ['x', 'm'], ['x', 'z'], ['x', 'z', 'm'], ['x', 'df'], ['x', 'df', 'm'], ['x', 'df', 'z'], ['x', 'df', 'z', 'm']])])
def test_contract(input_data, expected):
    assert powerset(*input_data) == expected
