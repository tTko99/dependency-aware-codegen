"""31 distinct authored standard-library API contracts, prepared before inference."""

from scripts.horizontal_prepare import test_code


def authored_specs():
    result = []

    def add(name, category, requirement, imports, signature, bad, good, rows):
        source = imports + "\n\ndef solve" + signature + ":\n" + bad + "\n"
        reference = imports + "\n\ndef solve" + signature + ":\n" + good + "\n"
        spec = {
            "id": "api200_" + name,
            "category": category,
            "requirement": requirement + " Preserve solve signature.",
            "source": source,
            "reference": reference,
            "rows": rows,
            "errors": [],
            "extra_tests": "",
            "provenance": {
                "kind": "authored_api_scenario",
                "production_bug": False,
                "family": name,
                "author": "project evaluation assistant",
                "method": "Distinct explicit API contract with authored defect, tests and reference before model evaluation.",
                "license": "project-authored fixture",
            },
        }
        spec["tests"] = test_code(spec)
        result.append(spec)

    add(
        "binomial",
        "api_name",
        "Return the number of unordered k-element selections from n distinct elements, for integers 0 <= k <= n.",
        "import math",
        "(n, k)",
        "    return math.binomial(n, k)",
        "    return math.comb(n, k)",
        [((5, 2), 10), ((0, 0), 1), ((8, 0), 1), ((8, 8), 1), ((10, 3), 120)],
    )
    add(
        "permutations_count",
        "api_name",
        "Return the number of ordered k-element arrangements without replacement from n distinct elements.",
        "import math",
        "(n, k)",
        "    return math.permutations(n, k)",
        "    return math.perm(n, k)",
        [((5, 2), 20), ((0, 0), 1), ((8, 0), 1), ((4, 4), 24), ((10, 3), 720)],
    )
    add(
        "integer_square_root",
        "api_name",
        "Return the exact floor of the square root of a nonnegative integer, including integers too large for reliable float conversion.",
        "import math",
        "(n)",
        "    return math.integer_sqrt(n)",
        "    return math.isqrt(n)",
        [((0,), 0), ((15,), 3), ((16,), 4), ((10**40 - 1,), 10**20 - 1)],
    )
    add(
        "product_identity",
        "api_name",
        "Return the product of numeric values. The empty product is 1.",
        "import math",
        "(values)",
        "    return math.product(values)",
        "    return math.prod(values)",
        [(([2, 3, 4],), 24), (([],), 1), (([0, 5],), 0), (([-2, 3],), -6)],
    )
    add(
        "least_common_multiple",
        "api_name",
        "Return the nonnegative least common multiple of two integers; any zero input yields zero.",
        "import math",
        "(a, b)",
        "    return math.least_common_multiple(a, b)",
        "    return math.lcm(a, b)",
        [((6, 8), 24), ((-6, 8), 24), ((0, 5), 0), ((7, 7), 7), ((0, 0), 0)],
    )
    add(
        "all_modes",
        "api_contract",
        "Return every most frequent value, ordered by first occurrence; empty input returns an empty list.",
        "import statistics",
        "(values)",
        "    return [statistics.mode(values)]",
        "    return statistics.multimode(values)",
        [(([1, 2, 1, 2, 3],), [1, 2]), (([3, 2, 3],), [3]), (([],), []), (([4, 5],), [4, 5])],
    )
    add(
        "lower_median",
        "api_contract",
        "Return the lower middle observed value for even length, ordinary middle value for odd length; input is nonempty.",
        "import statistics",
        "(values)",
        "    return statistics.median(values)",
        "    return statistics.median_low(values)",
        [(([1, 4],), 1), (([5, 1, 3],), 3), (([9],), 9), (([6, 2, 4, 8],), 4)],
    )
    add(
        "sample_standard_deviation",
        "api_contract",
        "Return the sample standard deviation of at least two numeric values, rounded to six decimal places, using the n-1 denominator.",
        "import statistics",
        "(values)",
        "    return round(statistics.pstdev(values), 6)",
        "    return round(statistics.stdev(values), 6)",
        [(([1, 3],), 1.414214), (([2, 2, 2],), 0), (([1, 2, 3],), 1)],
    )
    add(
        "harmonic_average",
        "api_name",
        "Return the harmonic mean of a nonempty positive numeric sequence.",
        "import statistics",
        "(values)",
        "    return statistics.hmean(values)",
        "    return statistics.harmonic_mean(values)",
        [(([1, 1],), 1), (([2, 6],), 3), (([5],), 5), (([3, 3, 3],), 3)],
    )
    add(
        "geometric_average",
        "api_name",
        "Return the geometric mean of positive values rounded to six decimal places.",
        "import statistics",
        "(values)",
        "    return round(statistics.gmean(values), 6)",
        "    return round(statistics.geometric_mean(values), 6)",
        [(([1, 16],), 4), (([2, 8],), 4), (([5],), 5), (([1, 1, 1],), 1)],
    )
    add(
        "adjacent_pairs",
        "api_name",
        "Return consecutive overlapping pairs as a list of tuples. Fewer than two inputs yield no pairs.",
        "import itertools",
        "(values)",
        "    return list(itertools.adjacent_pairs(values))",
        "    return list(itertools.pairwise(values))",
        [(([1, 2, 3],), [(1, 2), (2, 3)]), (([],), []), (([7],), []), (([4, 4],), [(4, 4)])],
    )
    add(
        "flatten_one_level",
        "api_contract",
        "Flatten exactly one level of a list of iterables, preserving input order.",
        "import itertools",
        "(groups)",
        "    return list(itertools.chain(groups))",
        "    return list(itertools.chain.from_iterable(groups))",
        [
            (([[1, 2], [], [3]],), [1, 2, 3]),
            (([],), []),
            (([["ab"], ["cd"]],), ["ab", "cd"]),
            (([[[1]], [2]],), [[1], 2]),
        ],
    )
    add(
        "longest_zip",
        "api_keyword",
        "Pair all items from two lists, filling missing positions with the provided fill value.",
        "import itertools",
        "(a, b, fill)",
        "    return list(itertools.zip_longest(a, b, default=fill))",
        "    return list(itertools.zip_longest(a, b, fillvalue=fill))",
        [
            (([1, 2], [3], 0), [(1, 3), (2, 0)]),
            (([], [3], None), [(None, 3)]),
            (([], [], 0), []),
            (([1], [2, 3], -1), [(1, 2), (-1, 3)]),
        ],
    )
    add(
        "right_insertion",
        "api_contract",
        "Return the insertion index after existing equal elements in an ascending sorted sequence.",
        "import bisect",
        "(values, target)",
        "    return bisect.bisect_left(values, target)",
        "    return bisect.bisect_right(values, target)",
        [(([1, 2, 2, 4], 2), 3), (([], 3), 0), (([1, 4], 0), 0), (([1, 4], 8), 2)],
    )
    add(
        "largest_values",
        "api_arguments",
        "Return up to n largest values in descending order, retaining duplicates; nonnegative n.",
        "import heapq",
        "(values, n)",
        "    return heapq.nlargest(values, n)",
        "    return heapq.nlargest(n, values)",
        [(([1, 4, 4, 2], 3), [4, 4, 2]), (([1, 2], 0), []), (([], 3), []), (([1, 2], 5), [2, 1])],
    )
    add(
        "deque_rotation",
        "api_return",
        "Rotate the sequence to the right by k positions (negative k rotates left); return a list and do not mutate the input.",
        "from collections import deque",
        "(values, k)",
        "    queue = deque(values)\n    return queue.rotate(k)",
        "    queue = deque(values)\n    queue.rotate(k)\n    return list(queue)",
        [
            (([1, 2, 3], 1), [3, 1, 2]),
            (([1, 2, 3], -1), [2, 3, 1]),
            (([], 9), []),
            (([1, 2], 4), [1, 2]),
        ],
    )
    add(
        "signed_counter",
        "api_contract",
        "Subtract right counts from left counts, returning a dict that retains zero and negative counts for every key present in either input.",
        "from collections import Counter",
        "(left, right)",
        "    return dict(Counter(left) - Counter(right))",
        "    counts = Counter(left)\n    counts.subtract(right)\n    return dict(counts)",
        [
            (({"a": 1, "b": 2}, {"a": 2}), {"a": -1, "b": 2}),
            (({"a": 1}, {"a": 1}), {"a": 0}),
            (({}, {"x": 2}), {"x": -2}),
            (({}, {}), {}),
        ],
    )
    add(
        "json_unicode",
        "api_keyword",
        "Serialize the mapping as JSON with literal Unicode characters and sorted keys, using default JSON spacing.",
        "import json",
        "(record)",
        "    return json.dumps(record, sort_keys=True)",
        "    return json.dumps(record, sort_keys=True, ensure_ascii=False)",
        [
            (({"x": "中文"},), '{"x": "中文"}'),
            (({"b": 2, "a": 1},), '{"a": 1, "b": 2}'),
            (({},), "{}"),
            (({"x": "é"},), '{"x": "é"}'),
        ],
    )
    add(
        "json_duplicate_pairs",
        "api_contract",
        "Parse a flat JSON object into an ordered list of key/value tuples, retaining duplicate keys.",
        "import json",
        "(text)",
        "    record = json.loads(text)\n    return list(record.items())",
        "    return json.loads(text, object_pairs_hook=list)",
        [
            (('{"a":1,"a":2}',), [("a", 1), ("a", 2)]),
            (("{}",), []),
            (('{"b":false,"x":null}',), [("b", False), ("x", None)]),
        ],
    )
    add(
        "urlencode_sequences",
        "api_keyword",
        "Encode a sequence of key/value pairs as a URL query, expanding list values into repeated keys and omitting empty lists.",
        "from urllib.parse import urlencode",
        "(pairs)",
        "    return urlencode(pairs)",
        "    return urlencode(pairs, doseq=True)",
        [
            (([("a", [1, 2]), ("b", "x y")],), "a=1&a=2&b=x+y"),
            (([("a", [])],), ""),
            (([],), ""),
            (([("q", "+")],), "q=%2B"),
        ],
    )
    add(
        "url_defragment",
        "api_return",
        "Return just the URL before the fragment separator, preserving the query and encoded characters.",
        "from urllib.parse import urldefrag",
        "(url)",
        "    return urldefrag(url)",
        "    return urldefrag(url).url",
        [
            (("https://a/x?q=1#part",), "https://a/x?q=1"),
            (("a%23b#c",), "a%23b"),
            (("plain",), "plain"),
            (("",), ""),
        ],
    )
    add(
        "regex_split_delimiters",
        "api_contract",
        "Split on each comma or semicolon, retaining empty fields but not delimiter characters.",
        "import re",
        "(text)",
        '    return re.split(r"([,;])", text)',
        '    return re.split(r"[,;]", text)',
        [
            (("a,b;c",), ["a", "b", "c"]),
            (("a,,b;",), ["a", "", "b", ""]),
            (("",), [""]),
            (("abc",), ["abc"]),
        ],
    )
    add(
        "regex_full_matches",
        "api_return",
        "Return each complete ASCII letter-plus-digit token matched by [A-Za-z]+[0-9]+, in order, not separate capture groups.",
        "import re",
        "(text)",
        '    return re.findall(r"([A-Za-z]+)([0-9]+)", text)',
        '    return re.findall(r"[A-Za-z]+[0-9]+", text)',
        [(("ab12 cd3",), ["ab12", "cd3"]), (("none",), []), (("x1x2",), ["x1", "x2"]), (("",), [])],
    )
    add(
        "iso_week_year",
        "api_return",
        "Return (ISO week-numbering year, ISO week, ISO weekday) for a Gregorian date, with Monday=1.",
        "from datetime import date",
        "(year, month, day)",
        "    d = date(year, month, day)\n    iso = d.isocalendar()\n    return year, iso.week, d.weekday()",
        "    d = date(year, month, day)\n    iso = d.isocalendar()\n    return iso.year, iso.week, iso.weekday",
        [
            ((2021, 1, 1), (2020, 53, 5)),
            ((2024, 1, 1), (2024, 1, 1)),
            ((2020, 12, 31), (2020, 53, 4)),
        ],
    )
    add(
        "bounded_fraction",
        "api_name",
        "Approximate a decimal string by a Fraction whose denominator is at most the provided positive bound; return numerator and denominator.",
        "from fractions import Fraction",
        "(text, bound)",
        "    value = Fraction(text)\n    approx = value.limit_denominators(bound)\n    return approx.numerator, approx.denominator",
        "    value = Fraction(text)\n    approx = value.limit_denominator(bound)\n    return approx.numerator, approx.denominator",
        [
            (("0.3333333", 10), (1, 3)),
            (("3.14159", 10), (22, 7)),
            (("0", 5), (0, 1)),
            (("-0.5", 10), (-1, 2)),
        ],
    )
    add(
        "absolute_closeness",
        "api_keyword",
        "Return whether two numbers differ by at most tolerance, using only absolute tolerance, not relative tolerance.",
        "import math",
        "(a, b, tolerance)",
        "    return math.isclose(a, b, rel_tol=tolerance)",
        "    return math.isclose(a, b, rel_tol=0, abs_tol=tolerance)",
        [
            ((0, 0.0001, 0.001), True),
            ((1000, 1001, 0.01), False),
            ((2, 2, 0), True),
            ((-1, 1, 2), True),
        ],
    )
    add(
        "reduce_empty_sum",
        "api_arguments",
        "Return the sum using an integer-zero identity, including zero for an empty input.",
        "from functools import reduce\nfrom operator import add",
        "(values)",
        "    return reduce(add, values)",
        "    return reduce(add, values, 0)",
        [(([],), 0), (([1, 2, 3],), 6), (([-1, 1],), 0), (([8],), 8)],
    )
    add(
        "multi_itemgetter",
        "api_arguments",
        "Select the values at exactly two given indices, returning a tuple in the requested index order.",
        "from operator import itemgetter",
        "(values, indices)",
        "    return itemgetter(indices)(values)",
        "    return itemgetter(*indices)(values)",
        [
            (([4, 5, 6], [2, 0]), (6, 4)),
            ((["a", "b"], [0, 0]), ("a", "a")),
            (([1, 2, 3], [-1, 1]), (3, 2)),
        ],
    )
    add(
        "common_indentation",
        "api_name",
        "Remove common leading whitespace from all nonblank lines using textwrap dedent semantics.",
        "import textwrap",
        "(text)",
        "    return textwrap.unindent(text)",
        "    return textwrap.dedent(text)",
        [(("  a\n    b\n",), "a\n  b\n"), (("x",), "x"), (("",), ""), (("    a\n    b",), "a\nb")],
    )
    add(
        "wrap_long_tokens",
        "api_keyword",
        "Wrap text to the given positive width, without breaking long words or at hyphens; return a list of lines.",
        "import textwrap",
        "(text, width)",
        "    return textwrap.wrap(text, width=width)",
        "    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)",
        [
            (("abcdefgh xy", 4), ["abcdefgh", "xy"]),
            (("ab-cd ef", 4), ["ab-cd", "ef"]),
            (("", 3), []),
            (("a bb c", 4), ["a bb", "c"]),
        ],
    )
    add(
        "optional_template",
        "api_contract",
        "Substitute known dollar-template names and preserve unknown placeholders literally; escaped $$ becomes $. Inputs use valid template syntax.",
        "from string import Template",
        "(text, mapping)",
        "    template = Template(text)\n    return template.substitute(mapping)",
        "    template = Template(text)\n    return template.safe_substitute(mapping)",
        [
            (("$a $b", {"a": "yes"}), "yes $b"),
            (("$$${x}", {"x": 3}), "$3"),
            (("plain", {}), "plain"),
            (("$missing", {}), "$missing"),
        ],
    )
    assert len(result) == 31
    return result
