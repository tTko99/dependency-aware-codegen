import solution

def test_contract_0():
    assert solution.lcs_of_three('Reels', 'Reelsfor', 'ReelsforReels') == 5

def test_contract_1():
    assert solution.lcs_of_three('abcd1e2', 'bc12ea', 'bd1ea') == 3
