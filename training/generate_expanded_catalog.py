from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from depguard.utils.jsonl import write_jsonl

VARIANT_TOKEN = "__V__"


@dataclass(frozen=True)
class Template:
    template_id: str
    library: str
    mutation_type: str
    original_api: str
    requirement: str
    valid_code: str
    test_code: str
    mutation: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/expanded_api_examples.jsonl")
    parser.add_argument("--variants", type=int, default=8)
    args = parser.parse_args(argv)
    if args.variants < 2:
        raise ValueError("At least two variants per template are required")

    templates = build_templates()
    records = render_catalog(templates, args.variants)
    write_jsonl(Path(args.output), records)
    print(
        f"wrote {len(records)} records from {len(templates)} templates "
        f"across {len({template.library for template in templates})} libraries"
    )
    return 0


def render_catalog(templates: list[Template], variants: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for template in templates:
        for variant in range(1, variants + 1):
            records.append(
                {
                    "id": f"{template.template_id}_v{variant:02d}",
                    "leakage_group": template.template_id,
                    "template_id": template.template_id,
                    "library": template.library,
                    "original_api": template.original_api,
                    "requirement": _render(template.requirement, variant),
                    "valid_code": _render(template.valid_code, variant),
                    "test_code": _render(template.test_code, variant),
                    "mutation": _render_value(template.mutation, variant),
                }
            )
    return records


def build_templates() -> list[Template]:
    templates = (
        package_templates()
        + module_templates()
        + class_templates()
        + function_templates()
        + method_templates()
        + keyword_templates()
        + argument_count_templates()
    )
    ids = [template.template_id for template in templates]
    apis = [template.original_api for template in templates]
    if len(templates) != 70:
        raise AssertionError(f"Expected 70 templates, got {len(templates)}")
    if len(ids) != len(set(ids)):
        raise AssertionError("Template IDs must be unique")
    if len(apis) != len(set(apis)):
        duplicates = sorted(api for api in set(apis) if apis.count(api) > 1)
        raise AssertionError(f"Original APIs must be unique across templates: {duplicates}")
    return templates


def package_templates() -> list[Template]:
    mutation_type = "hallucinated_package"
    return [
        _package(
            "pkg_math_cos", "math", "math.cos", "math", "math_phantom_01",
            "Compute cosine zero and retain the variant marker.",
            "import math\nv = __V__\nresult = (math.cos(0), v)\n",
            "from solution import result\n\ndef test_result():\n    assert result == (1.0, __V__)\n",
            mutation_type,
        ),
        _package(
            "pkg_json_dumps", "json", "json.dumps", "json", "json_phantom_02",
            "Serialize a variant value to JSON.",
            "import json\nv = __V__\nresult = json.dumps({'value': v}, sort_keys=True)\n",
            "import json\nfrom solution import result\n\ndef test_result():\n    assert json.loads(result) == {'value': __V__}\n",
            mutation_type,
        ),
        _package(
            "pkg_statistics_median", "statistics", "statistics.median", "statistics", "statistics_phantom_03",
            "Compute the median of three consecutive values.",
            "import statistics\nv = __V__\nresult = statistics.median([v, v + 1, v + 2])\n",
            "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1\n",
            mutation_type,
        ),
        _package(
            "pkg_re_split", "re", "re.split", "re", "regex_phantom_04",
            "Split a comma-separated variant string.",
            "import re\nv = __V__\nresult = re.split(',', f'{v},x')\n",
            "from solution import result\n\ndef test_result():\n    assert result == [str(__V__), 'x']\n",
            mutation_type,
        ),
        _package(
            "pkg_numpy_sum", "numpy", "numpy.sum", "numpy", "numpy_phantom_05",
            "Sum an integer NumPy range.",
            "import numpy as np\nv = __V__\nresult = int(np.sum(np.arange(v + 1)))\n",
            "from solution import result\n\ndef test_result():\n    assert result == __V__ * (__V__ + 1) // 2\n",
            mutation_type,
        ),
        _package(
            "pkg_pandas_index", "pandas", "pandas.Index", "pandas", "pandas_phantom_06",
            "Find the maximum value in a pandas Index.",
            "import pandas as pd\nv = __V__\nresult = int(pd.Index([v, v + 1]).max())\n",
            "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1\n",
            mutation_type,
        ),
        _package(
            "pkg_yaml_safe_dump", "yaml", "yaml.safe_dump", "yaml", "yaml_phantom_07",
            "Serialize a mapping as safe YAML.",
            "import yaml\nv = __V__\nresult = yaml.safe_dump({'value': v})\n",
            "import yaml\nfrom solution import result\n\ndef test_result():\n    assert yaml.safe_load(result) == {'value': __V__}\n",
            mutation_type,
        ),
        _package(
            "pkg_requests_prepared", "requests", "requests.PreparedRequest", "requests", "requests_phantom_08",
            "Prepare an HTTP request without sending it.",
            "import requests\nv = __V__\nrequest = requests.PreparedRequest()\nrequest.prepare(method='GET', url=f'https://example.com/{v}')\nresult = request.url\n",
            "from solution import result\n\ndef test_result():\n    assert result == 'https://example.com/__V__'\n",
            mutation_type,
        ),
        _package(
            "pkg_scipy_logit", "scipy", "scipy.special.logit", "scipy.special", "scipy_phantom_09.special",
            "Compute the logit of one half and retain a marker.",
            "import scipy.special as special\nv = __V__\nresult = (float(special.logit(0.5)), v)\n",
            "from solution import result\n\ndef test_result():\n    assert result == (0.0, __V__)\n",
            mutation_type,
        ),
        _package(
            "pkg_dateutil_relativedelta", "dateutil", "dateutil.relativedelta.relativedelta", "dateutil.relativedelta", "dateutil_phantom_10.relativedelta",
            "Add variant days with dateutil relativedelta.",
            "import datetime\nimport dateutil.relativedelta as dr\nv = __V__\nresult = (datetime.date(2024, 1, 1) + dr.relativedelta(days=v)).day\n",
            "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1\n",
            mutation_type,
        ),
    ]


def module_templates() -> list[Template]:
    mutation_type = "hallucinated_module"
    return [
        _module("mod_urllib_parse", "urllib", "urllib.parse.quote", "urllib.parse", "urllib.magicparse_01", "api.quote", "Quote a URL component.", "import urllib.parse as api\nv = __V__\nresult = api.quote(f'a {v}')\n", "from solution import result\n\ndef test_result():\n    assert result == 'a%20__V__'\n", mutation_type),
        _module("mod_xml_elementtree", "xml", "xml.etree.ElementTree.fromstring", "xml.etree.ElementTree", "xml.etree.MagicTree02", "api.fromstring", "Parse an XML element.", "import xml.etree.ElementTree as api\nv = __V__\nresult = api.fromstring(f'<n>{v}</n>').text\n", "from solution import result\n\ndef test_result():\n    assert result == str(__V__)\n", mutation_type),
        _module("mod_email_utils", "email", "email.utils.parseaddr", "email.utils", "email.magicutils_03", "api.parseaddr", "Parse an email address.", "import email.utils as api\nv = __V__\nresult = api.parseaddr(f'User <u{v}@example.com>')[1]\n", "from solution import result\n\ndef test_result():\n    assert result == 'u__V__@example.com'\n", mutation_type),
        _module("mod_importlib_util", "importlib", "importlib.util.find_spec", "importlib.util", "importlib.magicutil_04", "api.find_spec", "Find an import specification.", "import importlib.util as api\nv = __V__\nresult = (api.find_spec('json') is not None, v)\n", "from solution import result\n\ndef test_result():\n    assert result == (True, __V__)\n", mutation_type),
        _module("mod_numpy_linalg", "numpy", "numpy.linalg.norm", "numpy.linalg", "numpy.magic_linalg_05", "api.norm", "Compute a vector norm.", "import numpy.linalg as api\nv = __V__\nresult = float(api.norm([v, 0]))\n", "from solution import result\n\ndef test_result():\n    assert result == float(__V__)\n", mutation_type),
        _module("mod_pandas_types", "pandas", "pandas.api.types.is_integer_dtype", "pandas.api.types", "pandas.api.magictypes_06", "api.is_integer_dtype", "Check a pandas integer dtype.", "import pandas as pd\nimport pandas.api.types as api\nv = __V__\nresult = (bool(api.is_integer_dtype(pd.Series([v]).dtype)), v)\n", "from solution import result\n\ndef test_result():\n    assert result == (True, __V__)\n", mutation_type),
        _module("mod_scipy_special", "scipy", "scipy.special.expit", "scipy.special", "scipy.magic_special_07", "api.expit", "Compute a sigmoid value.", "import math\nimport scipy.special as api\nv = __V__\nresult = float(api.expit(v - 4))\n", "import math\nfrom solution import result\n\ndef test_result():\n    expected = 1 / (1 + math.exp(-(__V__ - 4)))\n    assert abs(result - expected) < 1e-12\n", mutation_type),
        _module("mod_requests_utils", "requests", "requests.utils.requote_uri", "requests.utils", "requests.magicutils_08", "api.requote_uri", "Quote spaces in a URI.", "import requests.utils as api\nv = __V__\nresult = api.requote_uri(f'https://example.com/a {v}')\n", "from solution import result\n\ndef test_result():\n    assert result == 'https://example.com/a%20__V__'\n", mutation_type),
        _module("mod_dateutil_parser", "dateutil", "dateutil.parser.parse", "dateutil.parser", "dateutil.magicparser_09", "api.parse", "Parse an ISO date with dateutil.", "import dateutil.parser as api\nv = __V__\nresult = api.parse(f'2024-01-{v:02d}').day\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n", mutation_type),
        _module("mod_json_decoder", "json", "json.decoder.JSONDecoder", "json.decoder", "json.magicdecoder_10", "api.JSONDecoder", "Decode JSON through its decoder module.", "import json.decoder as api\nv = __V__\nresult = api.JSONDecoder().decode(str(v))\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n", mutation_type),
    ]


def class_templates() -> list[Template]:
    mutation_type = "hallucinated_class"
    return [
        _call_template("class_pathlib_purepath", "pathlib", mutation_type, "pathlib.PurePath", "api.PurePath", "GhostPath01", "Create a pure path.", "import pathlib as api\nv = __V__\nresult = api.PurePath(f'folder{v}').name\n", "from solution import result\n\ndef test_result():\n    assert result == 'folder__V__'\n"),
        _call_template("class_datetime_timedelta", "datetime", mutation_type, "datetime.timedelta", "api.timedelta", "GhostDelta02", "Create a day interval.", "import datetime as api\nv = __V__\nresult = api.timedelta(days=v).days\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("class_collections_counter", "collections", mutation_type, "collections.Counter", "api.Counter", "FrequencyMap03", "Count repeated values.", "import collections as api\nv = __V__\nresult = api.Counter([v, v, 0])[v]\n", "from solution import result\n\ndef test_result():\n    assert result == 2\n"),
        _call_template("class_decimal_decimal", "decimal", mutation_type, "decimal.Decimal", "api.Decimal", "PreciseNumber04", "Construct a decimal value.", "import decimal as api\nv = __V__\nresult = str(api.Decimal(f'{v}.5'))\n", "from solution import result\n\ndef test_result():\n    assert result == f'{__V__}.5'\n"),
        _call_template("class_fractions_fraction", "fractions", mutation_type, "fractions.Fraction", "api.Fraction", "RationalNumber05", "Construct a fraction.", "import fractions as api\nv = __V__\nresult = api.Fraction(v, v + 1).numerator\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("class_pandas_timestamp", "pandas", mutation_type, "pandas.Timestamp", "pd.Timestamp", "DateStamp06", "Construct a pandas timestamp.", "import pandas as pd\nv = __V__\nresult = pd.Timestamp(f'2024-01-{v:02d}').day\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("class_pandas_categorical", "pandas", mutation_type, "pandas.Categorical", "pd.Categorical", "CategoryVector07", "Construct a pandas categorical array.", "import pandas as pd\nv = __V__\nresult = list(pd.Categorical([str(v), str(v)]))\n", "from solution import result\n\ndef test_result():\n    assert result == [str(__V__), str(__V__)]\n"),
        _call_template("class_requests_session", "requests", mutation_type, "requests.Session", "requests.Session", "HttpSession08", "Construct a requests session without network access.", "import requests\nv = __V__\nsession = requests.Session()\nresult = (len(session.headers) > 0, v)\n", "from solution import result\n\ndef test_result():\n    assert result == (True, __V__)\n"),
        _call_template("class_numpy_dtype", "numpy", mutation_type, "numpy.dtype", "np.dtype", "DataType09", "Construct a NumPy dtype.", "import numpy as np\nv = __V__\nresult = (np.dtype('int64').kind, v)\n", "from solution import result\n\ndef test_result():\n    assert result == ('i', __V__)\n"),
        _call_template("class_scipy_rotation", "scipy", mutation_type, "scipy.spatial.transform.Rotation", "api.Rotation", "SpatialRotation10", "Construct an identity spatial rotation.", "import scipy.spatial.transform as api\nv = __V__\nrotation = api.Rotation([0, 0, 0, 1])\nresult = (rotation.as_quat().tolist(), v)\n", "from solution import result\n\ndef test_result():\n    assert result == ([0.0, 0.0, 0.0, 1.0], __V__)\n"),
    ]


def function_templates() -> list[Template]:
    mutation_type = "hallucinated_function"
    return [
        _call_template("func_math_sqrt", "math", mutation_type, "math.sqrt", "api.sqrt", "square_root_01", "Compute an exact square root.", "import math as api\nv = __V__\nresult = api.sqrt(v * v)\n", "from solution import result\n\ndef test_result():\n    assert result == float(__V__)\n"),
        _call_template("func_json_loads", "json", mutation_type, "json.loads", "api.loads", "parse_json_02", "Parse a JSON number.", "import json as api\nv = __V__\nresult = api.loads(str(v))\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("func_statistics_mean", "statistics", mutation_type, "statistics.mean", "api.mean", "average_03", "Compute an arithmetic mean.", "import statistics as api\nv = __V__\nresult = api.mean([v, v + 2])\n", "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1\n"),
        _call_template("func_re_findall", "re", mutation_type, "re.findall", "api.findall", "find_all_04", "Find repeated digits.", "import re as api\nv = __V__\nresult = api.findall(r'\\d+', f'x{v}y{v}')\n", "from solution import result\n\ndef test_result():\n    assert result == [str(__V__), str(__V__)]\n"),
        _call_template("func_numpy_mean", "numpy", mutation_type, "numpy.mean", "np.mean", "average_05", "Compute a NumPy mean.", "import numpy as np\nv = __V__\nresult = float(np.mean([v, v + 2]))\n", "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1.0\n"),
        _call_template("func_pandas_to_datetime", "pandas", mutation_type, "pandas.to_datetime", "pd.to_datetime", "parse_datetime_06", "Parse a date with pandas.", "import pandas as pd\nv = __V__\nresult = pd.to_datetime(f'2024-01-{v:02d}').day\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("func_yaml_safe_load", "yaml", mutation_type, "yaml.safe_load", "api.safe_load", "secure_load_07", "Parse safe YAML.", "import yaml as api\nv = __V__\nresult = api.safe_load(f'value: {v}')['value']\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("func_scipy_softmax", "scipy", mutation_type, "scipy.special.softmax", "api.softmax", "normalized_exp_08", "Compute a softmax vector.", "import scipy.special as api\nv = __V__\nresult = api.softmax([0, 0]).tolist() + [v]\n", "from solution import result\n\ndef test_result():\n    assert result == [0.5, 0.5, __V__]\n"),
        _call_template("func_dateutil_isoparse", "dateutil", mutation_type, "dateutil.parser.isoparse", "api.isoparse", "iso_parse_09", "Parse an ISO timestamp.", "import dateutil.parser as api\nv = __V__\nresult = api.isoparse(f'2024-01-{v:02d}T00:00:00').day\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("func_requests_cookie_dict", "requests", mutation_type, "requests.utils.dict_from_cookiejar", "utils.dict_from_cookiejar", "cookie_dict_10", "Convert a cookie jar to a dictionary.", "import requests.cookies as cookies\nimport requests.utils as utils\nv = __V__\njar = cookies.cookiejar_from_dict({'v': str(v)})\nresult = utils.dict_from_cookiejar(jar)['v']\n", "from solution import result\n\ndef test_result():\n    assert result == str(__V__)\n"),
    ]


def method_templates() -> list[Template]:
    mutation_type = "hallucinated_method_or_attribute"
    return [
        _call_template("method_path_exists", "pathlib", mutation_type, "pathlib.Path.exists", "api.Path.exists", "exist_01", "Check that the current path exists.", "import pathlib as api\nv = __V__\npath = api.Path('.')\nresult = (api.Path.exists(path), v)\n", "from solution import result\n\ndef test_result():\n    assert result == (True, __V__)\n"),
        _call_template("method_date_isoformat", "datetime", mutation_type, "datetime.date.isoformat", "api.date.isoformat", "to_iso_02", "Format a date as ISO text.", "import datetime as api\nv = __V__\nday = api.date(2024, 1, v)\nresult = api.date.isoformat(day)\n", "from solution import result\n\ndef test_result():\n    assert result == f'2024-01-{__V__:02d}'\n"),
        _call_template("method_deque_append", "collections", mutation_type, "collections.deque.append", "api.deque.append", "append_right_03", "Append to a deque.", "import collections as api\nv = __V__\nvalues = api.deque([0])\napi.deque.append(values, v)\nresult = list(values)\n", "from solution import result\n\ndef test_result():\n    assert result == [0, __V__]\n"),
        _call_template("method_random_randint", "random", mutation_type, "random.Random.randint", "api.Random.randint", "random_integer_04", "Generate a bounded deterministic integer.", "import random as api\nv = __V__\nrng = api.Random(v)\nresult = api.Random.randint(rng, v, v)\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n"),
        _call_template("method_pattern_fullmatch", "re", mutation_type, "re.Pattern.fullmatch", "api.Pattern.fullmatch", "complete_match_05", "Fully match a repeated character pattern.", "import re as api\nv = __V__\npattern = api.compile(r'a+')\nresult = api.Pattern.fullmatch(pattern, 'a' * v) is not None\n", "from solution import result\n\ndef test_result():\n    assert result is True\n"),
        _call_template("method_series_sum", "pandas", mutation_type, "pandas.Series.sum", "pd.Series.sum", "total_06", "Sum a pandas Series through its method.", "import pandas as pd\nv = __V__\nseries = pd.Series([v, 1])\nresult = int(pd.Series.sum(series))\n", "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1\n"),
        _call_template("method_request_prepare", "requests", mutation_type, "requests.Request.prepare", "requests.Request.prepare", "build_07", "Prepare a requests Request.", "import requests\nv = __V__\nrequest = requests.Request('GET', f'https://example.com/{v}')\nresult = requests.Request.prepare(request).url\n", "from solution import result\n\ndef test_result():\n    assert result == 'https://example.com/__V__'\n"),
        _call_template("method_ndarray_tolist", "numpy", mutation_type, "numpy.ndarray.tolist", "np.ndarray.tolist", "to_list_08", "Convert a NumPy array to a list.", "import numpy as np\nv = __V__\narray = np.array([v, v + 1])\nresult = np.ndarray.tolist(array)\n", "from solution import result\n\ndef test_result():\n    assert result == [__V__, __V__ + 1]\n"),
        _call_template("method_decimal_quantize", "decimal", mutation_type, "decimal.Decimal.quantize", "api.Decimal.quantize", "round_to_09", "Quantize a decimal number.", "import decimal as api\nv = __V__\nnumber = api.Decimal(f'{v}.25')\nresult = str(api.Decimal.quantize(number, api.Decimal('0.1')))\n", "from solution import result\n\ndef test_result():\n    assert result == f'{__V__}.2'\n"),
        _call_template("method_fraction_limit", "fractions", mutation_type, "fractions.Fraction.limit_denominator", "api.Fraction.limit_denominator", "cap_denominator_10", "Limit a fraction denominator.", "import fractions as api\nv = __V__\nnumber = api.Fraction(v, v + 1)\nlimited = api.Fraction.limit_denominator(number, v + 1)\nresult = (limited.numerator, limited.denominator)\n", "from solution import result\n\ndef test_result():\n    assert result == (__V__, __V__ + 1)\n"),
    ]


def keyword_templates() -> list[Template]:
    mutation_type = "incorrect_argument_name"
    return [
        _keyword("kw_json_encoder", "json", "json.JSONEncoder", "api.JSONEncoder", "sort_keys", "sort_keyz_01", "Encode a sorted JSON object.", "import json as api\nv = __V__\nencoder = api.JSONEncoder(sort_keys=True)\nresult = encoder.encode({'b': v, 'a': 0})\n", "from solution import result\n\ndef test_result():\n    assert result.index('a') < result.index('b')\n", mutation_type),
        _keyword("kw_re_sub", "re", "re.sub", "api.sub", "count", "max_replacements_02", "Replace one matching digit.", "import re as api\nv = __V__\nresult = api.sub(r'\\d', 'x', str(v) + '9', count=1)\n", "from solution import result\n\ndef test_result():\n    assert result.startswith('x')\n", mutation_type),
        _keyword("kw_path_mkdir", "pathlib", "pathlib.Path.mkdir", "api.Path.mkdir", "parents", "parent_dirs_03", "Create a nested directory.", "import pathlib as api\nv = __V__\npath = api.Path(f'parent_{v}') / 'child'\napi.Path.mkdir(path, parents=True)\nresult = path.exists()\n", "from solution import result\n\ndef test_result():\n    assert result is True\n", mutation_type),
        _keyword("kw_dataframe_drop", "pandas", "pandas.DataFrame.drop", "pd.DataFrame.drop", "columns", "column_names_04", "Drop a DataFrame column.", "import pandas as pd\nv = __V__\nframe = pd.DataFrame({'x': [v], 'y': [0]})\nresult = pd.DataFrame.drop(frame, columns=['x']).columns.tolist()\n", "from solution import result\n\ndef test_result():\n    assert result == ['y']\n", mutation_type),
        _keyword("kw_numpy_concatenate", "numpy", "numpy.concatenate", "np.concatenate", "axis", "dimension_05", "Concatenate two NumPy arrays.", "import numpy as np\nv = __V__\nresult = np.concatenate([[v], [v + 1]], axis=0).tolist()\n", "from solution import result\n\ndef test_result():\n    assert result == [__V__, __V__ + 1]\n", mutation_type),
        _keyword("kw_requests_request", "requests", "requests.Request", "requests.Request", "method", "http_method_06", "Construct an HTTP request with keywords.", "import requests\nv = __V__\nresult = requests.Request(method='GET', url=f'https://example.com/{v}').method\n", "from solution import result\n\ndef test_result():\n    assert result == 'GET'\n", mutation_type),
        _keyword("kw_yaml_dump", "yaml", "yaml.dump", "api.dump", "sort_keys", "sorted_keys_07", "Dump sorted YAML keys.", "import yaml as api\nv = __V__\nresult = api.dump({'b': v, 'a': 0}, sort_keys=True)\n", "from solution import result\n\ndef test_result():\n    assert result.index('a:') < result.index('b:')\n", mutation_type),
        _keyword("kw_scipy_describe", "scipy", "scipy.stats.describe", "api.describe", "axis", "dimension_08", "Describe a numeric sequence.", "import scipy.stats as api\nv = __V__\nresult = int(api.describe([v, v + 1], axis=0).nobs)\n", "from solution import result\n\ndef test_result():\n    assert result == 2\n", mutation_type),
        _keyword("kw_datetime_isoformat", "datetime", "datetime.datetime.isoformat", "api.datetime.isoformat", "sep", "separator_09", "Format a datetime with a space separator.", "import datetime as api\nv = __V__\nvalue = api.datetime(2024, 1, v, 3, 4)\nresult = api.datetime.isoformat(value, sep=' ')\n", "from solution import result\n\ndef test_result():\n    assert result == f'2024-01-{__V__:02d} 03:04:00'\n", mutation_type),
        _keyword("kw_statistics_quantiles", "statistics", "statistics.quantiles", "api.quantiles", "n", "partitions_10", "Compute quartile cut points.", "import statistics as api\nv = __V__\nresult = len(api.quantiles([v, v + 1, v + 2, v + 3], n=4))\n", "from solution import result\n\ndef test_result():\n    assert result == 3\n", mutation_type),
    ]


def argument_count_templates() -> list[Template]:
    mutation_type = "incorrect_argument_count"
    return [
        _arguments("argc_math_factorial", "math", "math.factorial", "api.factorial", [], "Compute a factorial.", "import math as api\nv = __V__\nresult = api.factorial(v)\n", "import math\nfrom solution import result\n\ndef test_result():\n    assert result == math.factorial(__V__)\n", mutation_type),
        _arguments("argc_json_decoder", "json", "json.JSONDecoder.decode", "api.JSONDecoder.decode", [], "Decode a JSON integer through a decoder.", "import json as api\nv = __V__\ndecoder = api.JSONDecoder()\nresult = api.JSONDecoder.decode(decoder, str(v))\n", "from solution import result\n\ndef test_result():\n    assert result == __V__\n", mutation_type),
        _arguments("argc_statistics_fmean", "statistics", "statistics.fmean", "api.fmean", [], "Compute a floating-point mean.", "import statistics as api\nv = __V__\nresult = api.fmean([v, v + 2])\n", "from solution import result\n\ndef test_result():\n    assert result == __V__ + 1.0\n", mutation_type),
        _arguments("argc_re_compile", "re", "re.compile", "api.compile", [], "Compile a regular expression.", "import re as api\nv = __V__\nresult = api.compile(str(v)).pattern\n", "from solution import result\n\ndef test_result():\n    assert result == str(__V__)\n", mutation_type),
        _arguments("argc_numpy_reshape", "numpy", "numpy.reshape", "np.reshape", ["array"], "Reshape a NumPy array.", "import numpy as np\nv = __V__\narray = np.array([v, v + 1])\nresult = np.reshape(array, (1, 2)).tolist()\n", "from solution import result\n\ndef test_result():\n    assert result == [[__V__, __V__ + 1]]\n", mutation_type),
        _arguments("argc_pandas_concat", "pandas", "pandas.concat", "pd.concat", [], "Concatenate two pandas Series.", "import pandas as pd\nv = __V__\nresult = pd.concat([pd.Series([v]), pd.Series([v + 1])]).tolist()\n", "from solution import result\n\ndef test_result():\n    assert result == [__V__, __V__ + 1]\n", mutation_type),
        _arguments("argc_yaml_compose", "yaml", "yaml.compose", "api.compose", [], "Compose a YAML node.", "import yaml as api\nv = __V__\nresult = api.compose(f'value: {v}').value[0][1].value\n", "from solution import result\n\ndef test_result():\n    assert result == str(__V__)\n", mutation_type),
        _arguments("argc_requests_cookiejar", "requests", "requests.cookies.cookiejar_from_dict", "api.cookiejar_from_dict", ["{'v': str(v)}", "None", "True", "'extra'"], "Build a cookie jar from a dictionary.", "import requests.cookies as api\nv = __V__\nresult = len(api.cookiejar_from_dict({'v': str(v)}))\n", "from solution import result\n\ndef test_result():\n    assert result == 1\n", mutation_type),
        _arguments("argc_dateutil_gettz", "dateutil", "dateutil.tz.gettz", "api.gettz", ["'UTC'", "'extra'"], "Resolve a timezone name.", "import dateutil.tz as api\nv = __V__\nresult = (api.gettz('UTC') is not None, v)\n", "from solution import result\n\ndef test_result():\n    assert result == (True, __V__)\n", mutation_type),
        _arguments("argc_scipy_gmean", "scipy", "scipy.stats.gmean", "api.gmean", [], "Compute a geometric mean.", "import scipy.stats as api\nv = __V__\nresult = float(api.gmean([v, v]))\n", "from solution import result\n\ndef test_result():\n    assert abs(result - __V__) < 1e-12\n", mutation_type),
    ]


def _package(template_id: str, library: str, api: str, target: str, replacement: str, requirement: str, code: str, test: str, mutation_type: str) -> Template:
    return Template(template_id, library, mutation_type, api, requirement, code, test, {"type": mutation_type, "operation": "rename_import", "target": target, "replacement": replacement, "original_api": api, "expected_invalid_packages": [replacement.split(".", maxsplit=1)[0]], "expected_invalid_apis": []})


def _module(template_id: str, library: str, api: str, target: str, replacement: str, raw_call: str, requirement: str, code: str, test: str, mutation_type: str) -> Template:
    suffix = api.removeprefix(target + ".")
    expected = f"{replacement}.{suffix}"
    return Template(template_id, library, mutation_type, api, requirement, code, test, {"type": mutation_type, "operation": "rename_import", "target": target, "replacement": replacement, "original_api": api, "raw_call": raw_call, "expected_invalid_packages": [], "expected_invalid_apis": [expected]})


def _call_template(template_id: str, library: str, mutation_type: str, api: str, raw_call: str, replacement: str, requirement: str, code: str, test: str) -> Template:
    expected = f"{api.rsplit('.', maxsplit=1)[0]}.{replacement}"
    return Template(template_id, library, mutation_type, api, requirement, code, test, {"type": mutation_type, "operation": "rename_call", "target": raw_call, "replacement": replacement, "original_api": api, "expected_invalid_packages": [], "expected_invalid_apis": [expected]})


def _keyword(template_id: str, library: str, api: str, raw_call: str, keyword: str, replacement: str, requirement: str, code: str, test: str, mutation_type: str) -> Template:
    return Template(template_id, library, mutation_type, api, requirement, code, test, {"type": mutation_type, "operation": "rename_keyword", "target": raw_call, "target_keyword": keyword, "replacement": replacement, "original_api": api, "expected_invalid_packages": [], "expected_invalid_apis": [api]})


def _arguments(template_id: str, library: str, api: str, raw_call: str, args: list[str], requirement: str, code: str, test: str, mutation_type: str) -> Template:
    return Template(template_id, library, mutation_type, api, requirement, code, test, {"type": mutation_type, "operation": "replace_arguments", "target": raw_call, "args": args, "keywords": {}, "original_api": api, "expected_invalid_packages": [], "expected_invalid_apis": [api]})


def _render(value: str, variant: int) -> str:
    return value.replace(VARIANT_TOKEN, str(variant))


def _render_value(value: Any, variant: int) -> Any:
    if isinstance(value, str):
        return _render(value, variant)
    if isinstance(value, list):
        return [_render_value(item, variant) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, variant) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
