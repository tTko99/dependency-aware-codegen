def intervals(xs):
    result = []
    for a,b in sorted(xs):
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1],b))
        else:
            result.append((a,b))
    return result
