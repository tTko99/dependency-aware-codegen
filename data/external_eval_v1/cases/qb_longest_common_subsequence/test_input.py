# Adapted from QuixBugs 4257f44b0ff1181dedaedee6a447e133219fcebf; see ../../upstream/LICENSE.txt
import pytest
from solution import longest_common_subsequence

@pytest.mark.parametrize('input_data,expected', [(['headache', 'pentadactyl'], 'eadac'), (['daenarys', 'targaryen'], 'aary'), (['XMJYAUZ', 'MZJAWXU'], 'MJAU'), (['thisisatest', 'testing123testing'], 'tsitest'), (['1234', '1224533324'], '1234'), (['abcbdab', 'bdcaba'], 'bcba'), (['TATAGC', 'TAGCAG'], 'TAAG'), (['ABCBDAB', 'BDCABA'], 'BCBA'), (['ABCD', 'XBCYDQ'], 'BCD'), (['acbdegcedbg', 'begcfeubk'], 'begceb')])
def test_contract(input_data, expected):
    assert longest_common_subsequence(*input_data) == expected
