import random
random.seed(42)
from solution import car_race_collision






def check(car_race_collision):
    assert car_race_collision(2) == 4
    assert car_race_collision(3) == 9
    assert car_race_collision(4) == 16
    assert car_race_collision(8) == 64
    assert car_race_collision(10) == 100

check(car_race_collision)

def test_upstream_contract():
    random.seed(42)
    check(car_race_collision)
