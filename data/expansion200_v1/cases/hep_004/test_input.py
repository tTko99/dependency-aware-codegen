import random
random.seed(42)
from solution import mean_absolute_deviation






def check(mean_absolute_deviation):
    assert abs(mean_absolute_deviation([1.0, 2.0, 3.0]) - 2.0/3.0) < 1e-6
    assert abs(mean_absolute_deviation([1.0, 2.0, 3.0, 4.0]) - 1.0) < 1e-6
    assert abs(mean_absolute_deviation([1.0, 2.0, 3.0, 4.0, 5.0]) - 6.0/5.0) < 1e-6

check(mean_absolute_deviation)

def test_upstream_contract():
    random.seed(42)
    check(mean_absolute_deviation)
