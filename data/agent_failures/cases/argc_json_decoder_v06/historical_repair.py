import json as api
v = 6
decoder = api.JSONDecoder()
result = decoder.decode('{"key": 6}')
print(result)