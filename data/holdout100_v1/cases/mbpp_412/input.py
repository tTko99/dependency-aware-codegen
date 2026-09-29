def remove_odd(l):
    for i in l:
        if i % 2 != 1:
            l.remove(i)
    return l
