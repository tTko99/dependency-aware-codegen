import random
random.seed(42)
from solution import find_closest_elements






def check(find_closest_elements):
    assert find_closest_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2]) == (3.9, 4.0)
    assert find_closest_elements([1.0, 2.0, 5.9, 4.0, 5.0]) == (5.0, 5.9)
    assert find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2]) == (2.0, 2.2)
    assert find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0]) == (2.0, 2.0)
    assert find_closest_elements([1.1, 2.2, 3.1, 4.1, 5.1]) == (2.2, 3.1)

check(find_closest_elements)

def test_upstream_contract():
    random.seed(42)
    check(find_closest_elements)
