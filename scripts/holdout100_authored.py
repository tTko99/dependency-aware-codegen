"""New documented API contracts; no use of model evaluation outcomes."""


def specs():
    rows = []

    def add(name, module, category, requirement, signature, bad, good, visible, hidden):
        rows.append({'id':'stdlib_'+name, 'category':category,
                     'requirement':requirement+' Preserve solve signature.',
                     'reference':'import '+module+'\n\ndef solve'+signature+':\n'+good+'\n',
                     'source':'import '+module+'\n\ndef solve'+signature+':\n'+bad+'\n',
                     'visible':visible, 'hidden':hidden,
                     'provenance':{'kind':'authored_documented_contract','family':name,
                         'url':'https://docs.python.org/3.12/library/'+module+'.html',
                         'production_bug':False,'license':'project-authored fixture'}})

    add('relative_url','urllib.parse','api_usage','Resolve a relative URL against its base, including parent paths and absolute targets.',
        '(base, target)', '    return base + target', '    return urllib.parse.urljoin(base, target)',
        ["assert solve('https://a.org/p/', '../x') == 'https://a.org/x'", "assert solve('https://a.org/', 'https://b.org/y') == 'https://b.org/y'"],
        ["assert solve('https://a.org/p/index', 'z') == 'https://a.org/p/z'", "assert solve('https://a.org/p/', '/x?q=2') == 'https://a.org/x?q=2'", "assert solve('https://a.org/p', '') == 'https://a.org/p'"])
    add('form_decode','urllib.parse','api_usage','Decode form-encoded text: plus means space, percent escapes decode as UTF-8.',
        '(text)', '    return urllib.parse.unquote(text)', '    return urllib.parse.unquote_plus(text)',
        ["assert solve('a+b') == 'a b'", "assert solve('%2B+x') == '+ x'"],
        ["assert solve('++') == '  '", "assert solve('%E4%B8%AD+ok') == '中 ok'", "assert solve('') == ''"])
    add('ieee_remainder','math','boundary','Return IEEE 754 remainder: x minus nearest integer multiple of y, ties to even.',
        '(x, y)', '    return x % y', '    return math.remainder(x, y)',
        ['assert solve(7,4) == -1', 'assert solve(6,4) == -2'],
        ['assert solve(-7,4) == 1','assert solve(5,3) == -1','assert solve(3,-2) == -1'])
    add('fractional_parts','math','boundary','Return (fractional part, integer part) as floats, both retaining the input sign.',
        '(x)', '    return (x % 1, x // 1)', '    return math.modf(x)',
        ['assert solve(-2.75) == (-0.75,-2.0)','assert solve(3.5) == (0.5,3.0)'],
        ['assert solve(-0.125) == (-0.125,0.0)','assert solve(0) == (0.0,0.0)','assert solve(8.25) == (0.25,8.0)'])
    add('binary_decomposition','math','api_usage','Return mantissa and exponent such that x=m*2**e, abs(m) in [0.5,1) for nonzero x; zero gives (0,0).',
        '(x)', '    return (x / 2, 1)', '    return math.frexp(x)',
        ['assert solve(8) == (0.5,4)','assert solve(-6) == (-0.75,3)'],
        ['assert solve(0.125) == (0.5,-2)','assert solve(0) == (0.0,0)','assert solve(12) == (0.75,4)'])
    add('sign_transfer','math','boundary','Return abs(x) with the sign of y, including the sign of negative zero.',
        '(x, y)', '    return abs(x) if y >= 0 else -abs(x)', '    return math.copysign(x, y)',
        ['assert solve(5,-0.0) == -5','assert solve(-3,2) == 3'],
        ['assert solve(-8,-0.0) == -8','assert solve(2,-1) == -2','assert solve(-7,0.0) == 7'])
    add('initial_prefix_skip','itertools','algorithm','Skip the initial consecutive values below threshold, then retain every remaining value in original order.',
        '(values, threshold)', '    return [x for x in values if x >= threshold]', '    return list(itertools.dropwhile(lambda x: x < threshold, values))',
        ['assert solve([1,4,2,5],3) == [4,2,5]','assert solve([0,1],3) == []'],
        ['assert solve([5,0,1],4) == [5,0,1]','assert solve([],2) == []','assert solve([2,2,3,1],3) == [3,1]'])
    add('initial_prefix_take','itertools','algorithm','Return only the initial consecutive values below threshold; stop at the first value reaching threshold.',
        '(values, threshold)', '    return [x for x in values if x < threshold]', '    return list(itertools.takewhile(lambda x: x < threshold, values))',
        ['assert solve([1,4,2],3) == [1]','assert solve([4,1],3) == []'],
        ['assert solve([0,1,2],3) == [0,1,2]','assert solve([],0) == []','assert solve([1,2,2,0],2) == [1]'])
    add('selector_mask','itertools','data_processing','Select data where corresponding selector is truthy. Stop when either input is exhausted.',
        '(data, selectors)', '    return [x for x in data if x]', '    return list(itertools.compress(data, selectors))',
        ["assert solve(['a','b','c'],[1,0,1]) == ['a','c']",'assert solve([0,2],[1,0]) == [0]'],
        ["assert solve(['x','y','z'],[0,1]) == ['y']",'assert solve([], [1]) == []','assert solve([1,2],[False,True,True]) == [2]'])
    add('repeated_combinations','itertools','api_usage','Return all length-r combinations with repetition in input order. Input elements are distinct.',
        '(items, r)', '    return list(itertools.combinations(items, r))', '    return list(itertools.combinations_with_replacement(items, r))',
        ['assert solve([1,2],2) == [(1,1),(1,2),(2,2)]','assert solve([4],2) == [(4,4)]'],
        ["assert solve(['a','b'],2) == [('a','a'),('a','b'),('b','b')]",'assert solve([],0) == [()]','assert solve([],2) == []'])
    add('power_pairs','itertools','api_usage','For each (base, exponent) pair return base raised to exponent, preserving order. Empty input returns empty list.',
        '(pairs)', '    return list(map(pow, pairs))', '    return list(itertools.starmap(pow, pairs))',
        ['assert solve([(2,3),(3,2)]) == [8,9]','assert solve([(5,0)]) == [1]'],
        ['assert solve([]) == []','assert solve([(-2,3),(4,2)]) == [-8,16]','assert solve([(10,-1)]) == [0.1]'])
    add('consecutive_groups','itertools','data_processing','Return (value, run length) pairs for consecutive equal values; separated runs stay separate.',
        '(values)', '    return [(k, len(list(g))) for k,g in itertools.groupby(sorted(values))]', '    return [(k, len(list(g))) for k,g in itertools.groupby(values)]',
        ['assert solve([1,1,2,1]) == [(1,2),(2,1),(1,1)]',"assert solve(['b','a','a']) == [('b',1),('a',2)]"],
        ['assert solve([]) == []','assert solve([0,0,0]) == [(0,3)]','assert solve([2,1,2]) == [(2,1),(1,1),(2,1)]'])
    add('merge_sorted_streams','heapq','data_processing','Merge two sorted ascending sequences, retaining duplicates.',
        '(a, b)', '    return a + b', '    return list(heapq.merge(a,b))',
        ['assert solve([1,4],[2,3]) == [1,2,3,4]','assert solve([2,2],[1,2]) == [1,2,2,2]'],
        ['assert solve([],[-1,0]) == [-1,0]','assert solve([-3,0],[-2,1]) == [-3,-2,0,1]','assert solve([],[]) == []'])
    add('iso_calendar_inverse','datetime','boundary','Convert ISO week year, week and weekday (Monday=1) into Gregorian YYYY-MM-DD.',
        '(year, week, day)', '    return datetime.date(year,week,day).isoformat()', '    return datetime.date.fromisocalendar(year,week,day).isoformat()',
        ["assert solve(2020,1,1) == '2019-12-30'","assert solve(2020,53,7) == '2021-01-03'"],
        ["assert solve(2021,1,1) == '2021-01-04'","assert solve(2015,53,4) == '2015-12-31'","assert solve(2024,1,1) == '2024-01-01'"])
    add('json_prefix','json','data_processing','Parse a JSON value starting at character zero, allowing trailing data; return (value, end index). Input has no leading whitespace.',
        '(text)', '    return json.loads(text)', '    decoder = json.JSONDecoder()\n    return decoder.raw_decode(text)',
        ["assert solve('123 tail') == (123,3)","assert solve('[1,2]x') == ([1,2],5)"],
        ["assert solve('true!') == (True,4)","assert solve('null') == (None,4)","assert solve('{} {}') == ({},2)"])
    add('regex_spans','re','api_usage','Return start/end spans of all non-overlapping digit runs in a string.',
        '(text)', "    return re.findall(r'\\d+', text)", "    return [m.span() for m in re.finditer(r'\\d+', text)]",
        ["assert solve('a12b3') == [(1,3),(4,5)]","assert solve('123') == [(0,3)]"],
        ["assert solve('') == []","assert solve('abc') == []","assert solve('9 00') == [(0,1),(2,4)]"])
    add('path_suffix_chain','pathlib','data_processing','Return the list of all suffixes of a POSIX filename, treating a leading dot alone as a hidden-name prefix.',
        '(text)', '    return pathlib.PurePosixPath(text).suffix', '    return pathlib.PurePosixPath(text).suffixes',
        ["assert solve('archive.tar.gz') == ['.tar','.gz']","assert solve('a.txt') == ['.txt']"],
        ["assert solve('.bashrc') == []","assert solve('/a/b/file') == []","assert solve('.config.json') == ['.json']"])
    add('decimal_scale','decimal','boundary','Scale a decimal string by ten raised to integer exponent n, returning an exact decimal string.',
        '(text,n)', '    return str(decimal.Decimal(text) * n)', '    return str(decimal.Decimal(text).scaleb(n))',
        ["assert solve('1.25',2) == '125'","assert solve('12',-1) == '1.2'"],
        ["assert solve('2.5',0) == '2.5'","assert solve('-3.2',1) == '-32'","assert solve('0.01',2) == '1'"])
    add('complex_polar','cmath','api_usage','Return magnitude and phase angle in radians for a complex number.',
        '(z)', '    return (z.real,z.imag)', '    return cmath.polar(z)',
        ['assert solve(1j) == (1.0,1.5707963267948966)','assert solve(0+0j) == (0.0,0.0)'],
        ['assert solve(2+0j) == (2.0,0.0)','assert solve(-1+0j) == (1.0,3.141592653589793)','assert solve(2j) == (2.0,1.5707963267948966)'])
    add('fraction_decimal_string','fractions','boundary','Convert a decimal string to its exact numerator and denominator, returned as a tuple; do not round through a binary float.',
        '(text)', '    value = fractions.Fraction(float(text))\n    return (value.numerator,value.denominator)', '    value = fractions.Fraction(text)\n    return (value.numerator,value.denominator)',
        ["assert solve('0.1') == (1,10)","assert solve('1.25') == (5,4)"],
        ["assert solve('-0.3') == (-3,10)","assert solve('0') == (0,1)","assert solve('2.50') == (5,2)"])
    return rows
