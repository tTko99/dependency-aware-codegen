def pos_count(list):
    pos_count = 0
    for num in list:
        if num >= 0:
            pos_count += 2
    return pos_count
