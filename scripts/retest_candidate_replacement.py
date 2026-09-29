"""Agent-only frozen-task retest; never retries a started attempt."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.external_validation import (
    check_runtime,
    environment,
    fingerprint,
    implementation_files,
)
from evaluation.interview_benchmark import evaluate_case, make_model, now, save, verify_manifest
from evaluation.interview_metrics import real_pass

OUT = Path('results/candidate_replace_v1')
MANIFESTS = [Path('data') / n / 'manifest.json' for n in
             ['external_eval_v1', 'horizontal_eval_v1', 'expansion200_v1']]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected():
    hashes = json.loads((OUT / 'baseline_hashes.json').read_text())
    bad = [p for p, h in hashes.items() if digest(Path(p)) != h]
    if bad:
        raise ValueError(f'Protected files changed: {bad}')


def implementation():
    return fingerprint([*implementation_files(), Path(__file__)])


def report(cases):
    rows = [json.loads(p.read_text()) for p in sorted((OUT / 'cases').glob('*.json'))]
    defects = [r for r in rows if not r['is_control']]
    controls = [r for r in rows if r['is_control']]
    edits = [s for r in defects for s in r.get('trajectory', [])
             if (s.get('tool_call') or {}).get('name') in {'apply_patch', 'replace_candidate'}]
    stats = {'planned_defects': 200, 'planned_controls': 20,
             'recorded_defects': len(defects), 'agent_pass': sum(map(real_pass, defects)),
             'controls_recorded': len(controls), 'controls_pass': sum(map(real_pass, controls)),
             'controls_unmodified': sum(real_pass(r) and not r.get('agent_invoked', True) for r in controls),
             'terminations': dict(Counter(r['termination_reason'] for r in defects)),
             'edit_calls': len(edits), 'edits_accepted': sum(s['tool_result']['status']=='success' for s in edits),
             'edit_errors': dict(Counter(s['tool_result'].get('evidence', {}).get('error_code', 'OTHER')
                 for s in edits if s['tool_result']['status']!='success')),
             'updated': now(), 'baseline': {'pass':134,'planned':200,'unknown':3}}
    save(OUT / 'summary.json', stats)
    (OUT / 'cases.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    return stats


def main():
    protected()
    cases = [c for p in MANIFESTS for c in verify_manifest(p)['cases']]
    assert sum(not c['is_control'] for c in cases) == 200
    assert sum(c['is_control'] for c in cases) == 20
    config = json.loads(Path('configs/m7_qwen3_30b.json').read_text())
    old = json.loads(Path('results/expansion200_v1/freeze.json').read_text())
    fp = OUT / 'freeze.json'
    if not fp.exists():
        save(fp, {'created':now(), 'model_identity':old['model_identity'], 'resolved_config':config,
                  'implementation':implementation(), 'environment':environment(),
                  'cases':[c['id'] for c in cases], 'policy':'One Agent run per frozen case; no outcome tuning; old results preserved'})
    frozen = json.loads(fp.read_text())
    if frozen['implementation'] != implementation() or frozen['environment'] != environment():
        raise ValueError('Retest implementation/environment changed')
    model = make_model(config)
    check_runtime(model, frozen)
    probe_path = OUT / 'capability_probe.json'
    if not probe_path.exists():
        model._post_json('/api/generate', {'model':model.model_name, 'prompt':'', 'stream':False,
                         'keep_alive':'10m','options':{'num_ctx':16384,'temperature':0}})
        result = to_jsonable(run_probe(model, default_registry().specs, timeout_seconds=90, use_cache=False))
        save(probe_path, {'result':result,'runtime':check_runtime(model,frozen,loaded=True)})
    assert json.loads(probe_path.read_text())['result']['status']=='passed'
    print('Capability probe PASS',flush=True)
    for i, case in enumerate(cases,1):
        protected()
        if implementation()!=frozen['implementation']:
            raise ValueError('Implementation changed during evaluation')
        dest = OUT/'cases'/f"loop_{case['id']}.json"
        marker = OUT/'started'/f"{case['id']}.json"
        if dest.exists():
            continue
        if marker.exists():
            raise ValueError(f"Interrupted attempt requires audit: {case['id']}")
        runtime = check_runtime(model,frozen,loaded=True)
        save(marker, {'started':now(),'case':case['id']})
        row = evaluate_case(case,'loop',config,make_model(config),trigger_gate=True)
        row.update(runtime_before=runtime,run_id='candidate_replace_v1',resolved_config=config)
        # Persist the outcome BEFORE ancillary runtime inspection.
        save(dest,row)
        report(cases)
        print(f"{i}/{len(cases)} {case['id']}: {row['status']} ({row['latency']:.1f}s)",flush=True)
    protected()
    stats=report(cases)
    save(OUT/'completion.json',{'completed':now(),'protected_files_unchanged':True,'summary':stats})


if __name__ == '__main__':
    main()
