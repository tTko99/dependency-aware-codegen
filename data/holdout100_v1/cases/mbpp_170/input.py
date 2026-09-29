def sum_range_list(list1, m, n):
    sum_range = 0
    for i in range(m, n + 1, 2):
        sum_range += list1[i]
    return sum_range
