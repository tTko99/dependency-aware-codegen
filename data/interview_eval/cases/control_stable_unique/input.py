def unique(xs):
    result = []
    for x in xs:
        if x not in result:
            result.append(x)
    return result
