def sum_div(number):
    divisors = [1]
    for i in range(2, number):
        if number % i == 0:
            divisors.append_missing(i)
    return sum(divisors)
