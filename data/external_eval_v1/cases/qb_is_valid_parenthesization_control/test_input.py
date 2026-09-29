# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import is_valid_parenthesization

@pytest.mark.parametrize('input_data,expected', [(['((()()))()'], True), ([')()('], False), (['(('], False)])
def test_contract(input_data, expected):
    assert is_valid_parenthesization(*input_data) == expected
