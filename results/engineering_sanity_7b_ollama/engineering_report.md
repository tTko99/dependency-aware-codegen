# Phase 3 Small Engineering Sanity Set

This is a ten-case engineering sanity set for the external-file CLI workflow. It is not a statistically representative real-world benchmark. No suitable external or naturally model-generated examples were present in the repository, so all cases are honestly labeled as manually prepared.

## Results

| Case | Requirement | Initial problem | Detector finding | Initial execution/test | Repair (seconds) | Post-repair validation | Final execution/test | Outcome |
|---|---|---|---|---|---:|---|---|---|
| `package_textwrapx` | Dedent and strip `ready`. | Nonexistent package | `textwrapx` hallucinated package | Failed: `ModuleNotFoundError` | Yes (5.5644) | Passed | Passed | PASS |
| `function_statistics_average` | Compute the mean of 2, 5, and 8. | Nonexistent API | `statistics.average` hallucinated function | Failed: `AttributeError` | Yes (0.4235) | Passed | Passed | PASS |
| `class_collections_countmap` | Find the most common letter in banana. | Nonexistent class | `collections.CountMap` hallucinated class | Failed: `AttributeError` | Yes (0.5177) | Passed | Passed | PASS |
| `method_pathlib_get_suffix` | Get the suffix of `report.csv`. | Nonexistent method | `pathlib.Path.get_suffix` hallucinated function | Failed: `AttributeError` | Yes (0.4480) | Passed | Passed | PASS |
| `keyword_json_sort` | Serialize a dictionary with sorted keys. | Incorrect keyword | No static finding; execution found bad argument | Failed: `TypeError` | Yes (0.5065) | Passed | Passed | PASS |
| `arguments_json_loads` | Parse JSON and expose value 7. | Missing argument | `json.loads` incorrect arguments | Failed: `TypeError` | Yes (0.4784) | Passed | Passed | PASS |
| `functional_smallest_value` | Find the smallest of 7, 2, 9, and 4. | Functional error | No dependency/API finding; test exposed error | Failed: assertion (`9 != 2`) | Yes (0.4446) | Passed | Passed | PASS |
| `module_urllib_magicparse` | URL-encode `hello world`. | Nonexistent module | `urllib.magicparse.urlencode` hallucinated module | Failed: `ModuleNotFoundError` | Yes (0.4768) | Passed | Passed | PASS |
| `control_math_hypot` | Compute a 3-4 hypotenuse. | Correct control | None | Passed | No | Not applicable | Passed | PASS (`NO_REPAIR_NEEDED`) |
| `control_json_boolean` | Parse a JSON boolean. | Correct control | None | Passed | No | Not applicable | Passed | PASS (`NO_REPAIR_NEEDED`) |

All 10 cases passed. Eight cases received exactly one repair attempt; both controls remained untouched and did not invoke the model. Frozen SHA-256 checks confirmed that every external source and test file was unchanged after execution.
