"""Authored scenarios, explicitly synthetic; no claims of production provenance."""

from textwrap import dedent


def authored_cases():
    cases = []

    def add(name, category, requirement, imports, bad, good, rows, errors=(), extra=""):
        def program(body):
            return imports + "\n\ndef solve" + body.strip() + "\n"

        cases.append(
            {
                "id": "auth_" + name,
                "category": category,
                "requirement": requirement
                + " Preserve the solve signature; do not mutate caller inputs.",
                "source": program(bad),
                "reference": program(good),
                "rows": rows,
                "errors": list(errors),
                "extra_tests": dedent(extra),
                "provenance": {
                    "kind": "authored_scenario",
                    "production_bug": False,
                    "author": "project evaluation assistant",
                    "method": "Explicit contract, authored reference and defective implementation before model evaluation",
                    "family": name,
                    "license": "project-authored evaluation fixture",
                },
            }
        )

    add(
        "mean_api",
        "api",
        "Return the arithmetic mean of a nonempty numeric sequence.",
        "import statistics",
        "(values):\n    return statistics.average(values)",
        "(values):\n    return statistics.mean(values)",
        [(([2, 4, 9],), 5), (([-2, 2],), 0), (([3],), 3)],
    )
    add(
        "population_variance",
        "api",
        "Return population variance, including zero for one observation.",
        "import statistics",
        "(values):\n    return statistics.variance(values)",
        "(values):\n    return statistics.pvariance(values)",
        [(([1, 3],), 1), (([7],), 0), (([2, 2, 2],), 0)],
    )
    add(
        "prefix_totals",
        "api",
        "Return a list of cumulative sums in input order; empty input gives an empty list.",
        "import itertools",
        "(values):\n    return list(itertools.cumulative_sum(values))",
        "(values):\n    return list(itertools.accumulate(values))",
        [(([2, -1, 4],), [2, 1, 5]), (([],), []), (([0],), [0])],
    )
    add(
        "query_parameters",
        "api",
        "Parse a URL query into a mapping from keys to lists; preserve duplicates and blank values; decode percent escapes and plus signs.",
        "from urllib.parse import parse_qs",
        "(query):\n    return parse_qs(query)",
        "(query):\n    return parse_qs(query, keep_blank_values=True)",
        [
            (("a=1&a=2&b=",), {"a": ["1", "2"], "b": [""]}),
            (("q=a+b&x=%2B",), {"q": ["a b"], "x": ["+"]}),
            (("",), {}),
        ],
    )
    add(
        "whole_identifier",
        "api",
        "Accept exactly ASCII letters or underscore followed by ASCII letters, digits or underscore; reject trailing characters and newlines.",
        "import re",
        "(text):\n    return re.match(r'[A-Za-z_][A-Za-z0-9_]*', text) is not None",
        "(text):\n    return re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', text) is not None",
        [
            (("valid_2",), True),
            (("a!",), False),
            (("a\n",), False),
            (("2a",), False),
            (("",), False),
        ],
    )
    add(
        "top_counts",
        "api",
        "Return up to k (item,count) pairs by descending frequency, preserving first-seen tie order; k=0 returns empty.",
        "from collections import Counter",
        "(values, k):\n    return Counter(values).most_frequent(k)",
        "(values, k):\n    return Counter(values).most_common(k)",
        [((["b", "a", "b", "c", "a"], 2), [("b", 2), ("a", 2)]), (([], 3), []), ((["x"], 0), [])],
    )
    add(
        "calendar_parse",
        "api",
        "Parse an ISO calendar date and return its ordinal; reject impossible dates with ValueError.",
        "import datetime",
        "(text):\n    return datetime.fromisoformat(text).toordinal()",
        "(text):\n    return datetime.date.fromisoformat(text).toordinal()",
        [(("2024-02-29",), 738945), (("0001-01-01",), 1)],
        [(("2023-02-29",), "ValueError")],
    )
    add(
        "money_rounding",
        "api",
        "Round a decimal string to exactly two decimal places using half-up rounding; return a string.",
        "from decimal import Decimal, ROUND_HALF_UP",
        "(text):\n    return str(Decimal(text).quantize(Decimal('0.01')))",
        "(text):\n    return str(Decimal(text).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))",
        [(("1.005",), "1.01"), (("-1.005",), "-1.01"), (("3",), "3.00"), (("2.674",), "2.67")],
    )
    add(
        "json_boolean",
        "data",
        "Read a JSON object and return its enabled boolean, default False when absent. String values true/false must be interpreted case-insensitively, not by nonempty-string truthiness.",
        "import json",
        "(text):\n    return bool(json.loads(text).get('enabled', False))",
        "(text):\n    value = json.loads(text).get('enabled', False)\n    return value.lower() == 'true' if isinstance(value, str) else bool(value)",
        [
            (('{"enabled":"false"}',), False),
            (('{"enabled":true}',), True),
            (("{}",), False),
            (('{"enabled":"TRUE"}',), True),
        ],
    )
    add(
        "nested_lookup",
        "data",
        "Follow a list of dictionary keys, returning default only when a key is missing or a non-dictionary is reached; preserve present false/zero/None.",
        "",
        "(record, keys, default):\n    for key in keys:\n        record = record.get(key) or default\n    return record",
        "(record, keys, default):\n    for key in keys:\n        if not isinstance(record, dict) or key not in record:\n            return default\n        record = record[key]\n    return record",
        [
            (({"a": {"b": 0}}, ["a", "b"], 9), 0),
            (({"a": None}, ["a"], 9), None),
            (({"a": 1}, ["a", "b"], 9), 9),
            (({"x": 2}, [], 9), {"x": 2}),
        ],
    )
    add(
        "record_grouping",
        "data",
        "Group record dictionaries by their kind field, preserving group and record order; missing kind belongs to None.",
        "",
        "(records):\n    result = {}\n    for record in records:\n        result[record.get('kind')] = [record]\n    return result",
        "(records):\n    result = {}\n    for record in records:\n        group = result.setdefault(record.get('kind'), [])\n        group.append(record)\n    return result",
        [
            (
                ([{"kind": "a", "n": 1}, {"kind": "a", "n": 2}],),
                {"a": [{"kind": "a", "n": 1}, {"kind": "a", "n": 2}]},
            ),
            (([{"n": 1}],), {None: [{"n": 1}]}),
            (([],), {}),
        ],
    )
    add(
        "merge_defaults",
        "data",
        "Merge default and supplied options; supplied values win even if False, zero or None. Do not modify either input.",
        "",
        "(defaults, supplied):\n    return dict(supplied, **defaults)",
        "(defaults, supplied):\n    result = dict(defaults)\n    result.update(supplied)\n    return result",
        [
            (({"a": 1, "b": 2}, {"a": 0}), {"a": 0, "b": 2}),
            (({"x": True}, {"x": False}), {"x": False}),
            (({}, {"x": None}), {"x": None}),
        ],
    )
    add(
        "numeric_record_order",
        "data",
        "Return records ordered by numeric score ascending, preserving ties; scores are numeric strings.",
        "",
        "(records):\n    return sorted(records, key=lambda row: row['score'])",
        "(records):\n    return sorted(records, key=lambda row: float(row['score']))",
        [
            (
                ([{"score": "10"}, {"score": "2"}, {"score": "-1"}],),
                [{"score": "-1"}, {"score": "2"}, {"score": "10"}],
            ),
            (([],), []),
        ],
    )
    add(
        "unique_records",
        "data",
        "Keep the first record for each id, preserving first-seen order. IDs are hashable.",
        "",
        "(records):\n    result = {r['id']: r for r in records}\n    return list(result.values())",
        "(records):\n    result = {}\n    for row in records:\n        if row['id'] not in result:\n            result[row['id']] = row\n    return list(result.values())",
        [
            (
                ([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}],),
                [{"id": 1, "v": "a"}, {"id": 2, "v": "c"}],
            ),
            (([],), []),
        ],
    )
    add(
        "pair_transpose",
        "data",
        "Transpose a rectangular list of rows to lists of columns; empty input returns []; reject ragged rows with ValueError.",
        "",
        "(rows):\n    return [list(column) for column in zip(*rows)]",
        '(rows):\n    if rows and any(len(row) != len(rows[0]) for row in rows):\n        raise ValueError("ragged")\n    return [list(column) for column in zip(*rows)]',
        [(([[1, 2], [3, 4]],), [[1, 3], [2, 4]]), (([],), []), (([[], []],), [])],
        [(([[1, 2], [3]],), "ValueError")],
    )
    add(
        "literal_prefix",
        "text",
        "Remove prefix exactly once only when text starts with that complete prefix; an empty prefix changes nothing.",
        "",
        "(text, prefix):\n    return text.lstrip(prefix)",
        "(text, prefix):\n    return text[len(prefix):] if prefix and text.startswith(prefix) else text",
        [
            (("foobar", "foo"), "bar"),
            (("ofobar", "foo"), "ofobar"),
            (("foofoo", "foo"), "foo"),
            (("abc", ""), "abc"),
        ],
    )
    add(
        "literal_separator",
        "text",
        "Split text on a literal nonempty separator, retaining empty fields; separator metacharacters have no special meaning.",
        "import re",
        "(text, separator):\n    return re.split(separator, text)",
        "(text, separator):\n    return text.split(separator)",
        [
            (("a.b..c", "."), ["a", "b", "", "c"]),
            (("a|b|", "|"), ["a", "b", ""]),
            (("", "::"), [""]),
        ],
    )
    add(
        "casefold_match",
        "text",
        "Compare two Unicode strings caselessly using Unicode case folding, without trimming whitespace.",
        "",
        "(left, right):\n    return left.lower() == right.lower()",
        "(left, right):\n    return left.casefold() == right.casefold()",
        [
            (("Straße", "STRASSE"), True),
            (("Σ", "ς"), True),
            (("a ", "a"), False),
            (("Hello", "hello"), True),
        ],
    )
    add(
        "line_endings",
        "text",
        "Return lines without line terminators, recognizing LF, CRLF and CR; do not add a final empty line for a terminal line ending.",
        "",
        "(text):\n    return text.split('\\n')",
        "(text):\n    return text.splitlines()",
        [(("a\r\nb\rc\n",), ["a", "b", "c"]), (("",), []), (("a\n\nb",), ["a", "", "b"])],
    )
    add(
        "quoted_tokens",
        "text",
        'Parse comma-separated fields with double-quoted fields; commas inside quotes are literal and doubled quotes inside quotes denote one quote. Return [""] for empty input. Inputs are well-formed; no multiline records.',
        "",
        "(text):\n    return text.split(',')",
        """(text):
    fields, current, quoted = [], [], False
    empty = ''
    i = 0
    while i < len(text):
        char = text[i]
        if char == '"':
            if quoted and i + 1 < len(text) and text[i + 1] == '"':
                current.append('"')
                i += 1
            else:
                quoted = not quoted
        elif char == ',' and not quoted:
            fields.append(empty.join(current))
            current = []
        else:
            current.append(char)
        i += 1
    fields.append(empty.join(current))
    return fields""",
        [
            (('a,"b,c",d',), ["a", "b,c", "d"]),
            (('"a""b",',), ['a"b', ""]),
            (("",), [""]),
            (("a,,b",), ["a", "", "b"]),
        ],
    )
    add(
        "regex_replacement_literal",
        "text",
        "Replace all occurrences matching a regex with literal replacement text; backslashes in replacement text are not group references.",
        "import re",
        "(text, pattern, replacement):\n    return re.sub(pattern, replacement, text)",
        "(text, pattern, replacement):\n    return re.sub(pattern, lambda match: replacement, text)",
        [
            (("a1b2", r"\d", r"\1"), r"a\1b\1"),
            (("aaa", "a", "$"), "$$$"),
            (("abc", "z", "x"), "abc"),
        ],
    )
    add(
        "word_frequencies",
        "text",
        "Count whitespace-separated words case-insensitively using casefold; retain punctuation as part of a word and ignore repeated whitespace.",
        "",
        "(text):\n    result = {}\n    lowered = text.lower()\n    for word in lowered.split(' '):\n        result[word] = result.get(word, 0) + 1\n    return result",
        "(text):\n    result = {}\n    folded = text.casefold()\n    for word in folded.split():\n        result[word] = result.get(word, 0) + 1\n    return result",
        [(("A  a\tB\n",), {"a": 2, "b": 1}), (("Straße STRASSE",), {"strasse": 2}), (("",), {})],
    )
    add(
        "elapsed_days",
        "numeric_time",
        "Return elapsed time in seconds between two ISO datetimes, including days and negative differences.",
        "from datetime import datetime",
        "(start, end):\n    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds",
        "(start, end):\n    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)\n    return duration.total_seconds()",
        [
            (("2024-01-01", "2024-01-03"), 172800),
            (("2024-01-02", "2024-01-01"), -86400),
            (("2024-01-01T00:00:00", "2024-01-01T00:00:01.5"), 1.5),
        ],
    )
    add(
        "leap_century",
        "numeric_time",
        "Return whether a positive Gregorian year is a leap year.",
        "",
        "(year):\n    return year % 4 == 0",
        "(year):\n    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)",
        [((1900,), False), ((2000,), True), ((2024,), True), ((2023,), False), ((2100,), False)],
    )
    add(
        "next_calendar_day",
        "numeric_time",
        "Return the ISO date immediately after a valid input ISO date, including month and leap-year boundaries.",
        "from datetime import date, timedelta",
        "(text):\n    value = date.fromisoformat(text)\n    return date(value.year, value.month, value.day + 1).isoformat()",
        "(text):\n    following = date.fromisoformat(text) + timedelta(days=1)\n    return following.isoformat()",
        [
            (("2024-02-28",), "2024-02-29"),
            (("2024-02-29",), "2024-03-01"),
            (("2023-12-31",), "2024-01-01"),
        ],
    )
    add(
        "ceil_batches",
        "numeric_time",
        "Return number of capacity-sized batches required for n items, n >= 0 and capacity > 0, using exact integer arithmetic.",
        "",
        "(n, capacity):\n    return n // capacity",
        "(n, capacity):\n    return (n + capacity - 1) // capacity",
        [((10, 3), 4), ((0, 7), 0), ((12, 4), 3), ((10**20 + 1, 10), 10**19 + 1)],
    )
    add(
        "clamp_bounds",
        "numeric_time",
        "Clamp value to the inclusive lower/upper interval; reject lower > upper with ValueError.",
        "",
        "(value, lower, upper):\n    return min(lower, max(upper, value))",
        '(value, lower, upper):\n    if lower > upper:\n        raise ValueError("reversed bounds")\n    return max(lower, min(upper, value))',
        [((5, 0, 10), 5), ((-2, 0, 10), 0), ((20, 0, 10), 10), ((3, 2, 2), 2)],
        [((1, 3, 2), "ValueError")],
    )
    add(
        "decimal_total",
        "numeric_time",
        "Sum decimal strings exactly and return a fixed-point decimal string, preserving Decimal arithmetic rather than binary floating point.",
        "from decimal import Decimal",
        "(values):\n    return str(sum(float(x) for x in values))",
        '(values):\n    return format(sum((Decimal(x) for x in values), Decimal(0)), "f")',
        [
            ((["0.1", "0.2"],), "0.3"),
            (([],), "0"),
            ((["100000000000000000000", "1"],), "100000000000000000001"),
        ],
    )
    add(
        "rational_ratio",
        "numeric_time",
        "Return an exact reduced numerator/denominator pair for integer a divided by nonzero integer b; denominator must be positive.",
        "from fractions import Fraction",
        "(a, b):\n    value = Fraction(a / b)\n    return value.numerator, value.denominator",
        "(a, b):\n    value = Fraction(a, b)\n    return value.numerator, value.denominator",
        [((1, 3), (1, 3)), ((-2, -4), (1, 2)), ((0, 5), (0, 1)), ((10, 6), (5, 3))],
    )
    add(
        "fresh_accumulator",
        "state",
        "Return a new list containing the supplied value. Separate calls must be independent; preserve the optional bucket parameter and copy an explicitly supplied bucket.",
        "",
        "(value, bucket=[]):\n    bucket.append(value)\n    return bucket",
        "(value, bucket=None):\n    return ([] if bucket is None else list(bucket)) + [value]",
        [((1,), [1]), ((2,), [2]), ((3, [0]), [0, 3])],
        extra="""
        def test_independent_calls():
            assert solve('x') == ['x']
            assert solve('y') == ['y']
            original = [0]
            assert solve(1, original) == [0, 1]
            assert original == [0]
        """,
    )
    add(
        "safe_int",
        "state",
        "Convert valid integer strings to int; return the supplied default on TypeError or ValueError.",
        "",
        "(value, default):\n    try:\n        return int(value)\n    except TypeError:\n        return default",
        "(value, default):\n    try:\n        return int(value)\n    except (TypeError, ValueError):\n        return default",
        [(("12", 0), 12), (("bad", 7), 7), ((None, 3), 3), (("-2", 0), -2)],
    )
    add(
        "first_present",
        "state",
        "Return the first value that is not None, retaining zero, False and empty strings; return default when all are None.",
        "",
        "(values, default):\n    return next((x for x in values if x), default)",
        "(values, default):\n    return next((x for x in values if x is not None), default)",
        [
            (([None, 0, 1], 9), 0),
            (([None, "", "x"], 9), ""),
            (([], 9), 9),
            (([False, True], 9), False),
        ],
    )
    add(
        "immutable_sort",
        "state",
        "Return a sorted copy of values without changing the original list.",
        "",
        "(values):\n    values.sort()\n    return values",
        "(values):\n    return sorted(values)",
        [(([3, 1, 2],), [1, 2, 3]), (([],), [])],
        extra="""
        def test_does_not_mutate():
            values = [3, 1, 2]
            assert solve(values) == [1, 2, 3]
            assert values == [3, 1, 2]
        """,
    )
    add(
        "independent_rows",
        "state",
        "Build an n by m zero matrix whose rows are independent mutable lists; dimensions are nonnegative.",
        "",
        "(n, m):\n    return [[0] * m] * n",
        "(n, m):\n    return [[0] * m for _ in range(n)]",
        [((2, 2), [[0, 0], [0, 0]]), ((0, 3), [])],
        extra="""
        def test_row_independence():
            rows = solve(2, 2)
            rows[0][0] = 1
            assert rows[1] == [0, 0]
        """,
    )
    add(
        "drain_iterator",
        "state",
        "Return (count, total) for an iterable of numbers, including one-shot iterators.",
        "",
        "(values):\n    count = len(list(values))\n    return count, sum(values)",
        "(values):\n    count = total = 0\n    for value in values:\n        count += 1\n        total += value\n    return count, total",
        [(([1, 2, 3],), (3, 6)), (([],), (0, 0))],
        extra="""
        def test_iterator_consumed_once():
            assert solve(iter([1, 2, 3])) == (3, 6)
        """,
    )
    add(
        "filter_mapping",
        "state",
        "Return a new mapping without entries whose values are None, preserving false and zero values and leaving the original unchanged.",
        "",
        "(mapping):\n    for key in mapping:\n        if mapping[key] is None:\n            del mapping[key]\n    return mapping",
        "(mapping):\n    return {key: value for key, value in mapping.items() if value is not None}",
        [(({"a": None, "b": 0, "c": False},), {"b": 0, "c": False}), (({},), {})],
        extra="""
        def test_original_preserved():
            values = {'a': None, 'b': 2}
            assert solve(values) == {'b': 2}
            assert values == {'a': None, 'b': 2}
        """,
    )
    assert len(cases) == 36
    return cases
