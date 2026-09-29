from operator import itemgetter

def index_minimum(test_list):
    res = min(test_list, key=itemgetter(1))[1]
    return res
