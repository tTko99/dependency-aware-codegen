def odd_values_string(str):
    result = ''
    for i in range(len(str)):
        if i % 3 == 0:
            result = result + str[i]
    return result
