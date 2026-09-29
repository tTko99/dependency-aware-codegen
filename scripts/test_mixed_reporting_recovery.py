"""Audit that interrupted mixed-source attempts cannot improve measured costs."""
import copy
import json
from pathlib import Path

from evaluation.external_report import aggregate
from scripts.finalize_mixed_evidence import corrected


def test_unknown_result_keeps_denominator_but_excludes_cost_and_protocol():
    root = Path('results/horizontal_eval_v1/cases')
    names = ['public_split_after', 'auth_nested_lookup']
    rows = [json.loads((root / f'{condition}_{name}.json').read_text(encoding='utf-8'))
            for name in names for condition in ('one-shot', 'loop')]
    cases = [{'id': name, 'is_control': False} for name in names]
    stats = aggregate(cases, rows)
    before = copy.deepcopy((stats, rows))
    result = corrected(stats, rows)
    assert (stats, rows) == before
    assert result['conditions']['loop']['repair_pass']['denominator'] == 2
    assert result['conditions']['loop']['cost_repairs']['runs'] == 1
    assert result['paired_repair_outcomes']['interrupted_pair'] == 1
    assert result['tool_protocol']['denominator'] == 1
    assert result['strict_rescue']['numerator'] == 1
    assert not result['fully_observed']
