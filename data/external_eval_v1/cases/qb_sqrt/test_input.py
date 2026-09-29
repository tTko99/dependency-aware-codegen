# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import sqrt

@pytest.mark.parametrize('input_data,expected', [([2, 0.01], 1.4166666666666665), ([2, 0.5], 1.5), ([2, 0.3], 1.5), ([4, 0.2], 2), ([27, 0.01], 5.196164639727311), ([33, 0.05], 5.744627526262464), ([170, 0.03], 13.038404876679632)])
def test_contract(input_data, expected):
    assert sqrt(*input_data) == pytest.approx(expected, abs=input_data[-1])
