"""Ensure audited service loss cannot become a retry, PASS, or zero-cost sample."""
import json
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.external_report import aggregate
from scripts.finalize_mixed_evidence import corrected

ROOT = Path('results/expansion200_v1')


def test_first_49_pairs_remain_byte_identical():
    prior=json.loads((ROOT/'recovery/run_manifest_before_recovery.json').read_text(encoding='utf-8'))
    assert len(prior['artifact_hashes'])==98
    for name,digest in prior['artifact_hashes'].items():
        assert sha((ROOT/'cases'/name).read_bytes())==digest
    audit=json.loads((ROOT/'recovery/interruption.json').read_text(encoding='utf-8'))
    assert audit['artifact']=='loop_hep_154.json' and audit['retried'] is False


def test_interrupted_attempt_is_not_a_measured_zero_cost_or_pass():
    rows=[json.loads((ROOT/'cases'/name).read_text(encoding='utf-8')) for name in ['loop_hep_154.json','loop_hep_111.json']]
    interrupted=rows[0]
    assert interrupted['measurement_status']=='interrupted_unknown'
    assert interrupted['agent_invoked'] is None and interrupted['trajectory']==[]
    cases=[{'id':r['case_id'],'is_control':False} for r in rows]
    result=corrected(aggregate(cases,rows),rows)
    assert result['conditions']['loop']['cost_repairs']['runs']==1
    assert result['conditions']['loop']['repair_pass']['numerator']==0
    assert result['tool_protocol']['denominator']==1
    assert result['observed_attempts']==1 and not result['fully_observed']
