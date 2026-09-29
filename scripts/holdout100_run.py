"""Background preparation-to-evaluation workflow, with sealed final tests."""
import json
import time
from collections import Counter
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.runner import validate_candidate
from depguard.agent.safety import load_state
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.agent_benchmark import sha
from evaluation.external_validation import check_runtime, environment, fingerprint
from evaluation.interview_benchmark import evaluate_case, make_model, now, save, verify_manifest
from evaluation.interview_metrics import real_pass
from scripts.holdout100_prepare import DATA, OUT, verify_agent


def visible_case(case):
    return {key:value for key,value in case.items() if key not in {'reference_file','hidden_test_file','provenance','hashes'}}


def final_acceptance(case, row):
    # No subsequent model call: hidden evidence is never appended to messages.
    state=load_state(case['code_file'],case['hidden_test_file'],project_root=Path(case['code_file']).parent,
                     execution_timeout_seconds=10,validation_config={'required_checks':case['required_checks']})
    state.candidate_code=row['candidate_code']
    started=time.monotonic()
    try:
        result=validate_candidate(state,time.monotonic()+30)
        return {'status':'PASS' if result['host_status']=='PASS' else 'FAIL',
                'verification':result,'latency':time.monotonic()-started,'model_feedback':False,
                'candidate_sha256':sha(row['candidate_code'].encode()),
                'test_sha256':sha(Path(case['hidden_test_file']).read_bytes())}
    except Exception as exc:  # noqa: BLE001 - retain infrastructure failures distinctly
        return {'status':'ERROR','error_type':type(exc).__name__,'latency':time.monotonic()-started,'model_feedback':False}


def integrity(frozen):
    verify_agent()
    if environment()!=frozen['environment']:raise ValueError('Environment changed')
    for p,h in frozen['sha256'].items():
        if sha(Path(p).read_bytes())!=h:raise ValueError('Frozen artifact changed: '+p)


def report():
    rows=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((OUT/'cases').glob('*.json'))]
    summary={'planned':100,'recorded':len(rows),'visible_host_pass':sum(real_pass(r) for r in rows),
             'hidden_pass':sum(r['hidden_acceptance']['status']=='PASS' for r in rows),
             'joint_pass':sum(r['joint_pass'] for r in rows),
             'terminations':dict(Counter(r['termination_reason'] for r in rows)),
             'groups':{},'updated':now(),'complete':len(rows)==100}
    for group in sorted({r['source_group'] for r in rows}):
        values=[r for r in rows if r['source_group']==group]
        summary['groups'][group]={'recorded':len(values),'joint_pass':sum(r['joint_pass'] for r in values)}
    save(OUT/'summary.json',summary)
    (OUT/'cases.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    text=['# 未用于本项目开发的 100 例独立评估','',
          f"状态：{'全部完成' if len(rows)==100 else '运行中'}；记录 {len(rows)}/100。",'',
          f"可见验证通过：{summary['visible_host_pass']}；保留验收通过：{summary['hidden_pass']}；联合通过：{summary['joint_pass']}。",'',
          '联合通过要求 Agent 正常结束并通过可见宿主验证，同时通过未反馈给模型的保留测试。',
          '来源为 80 个 MBPP 契约的确定性人工变异和 20 个文档契约人工场景，均不冒充生产故障。',
          '这些任务未用于本项目此前开发；公开基准可能存在模型预训练重合，不能声称模型从未见过。',
          '开发/回归集 192/200 与本批分开报告，不合并修复率。安全拒绝、超时和协议失败不删除。','',
          '## 分来源','', '| 来源 | 已记录 | 联合通过 |','| --- | ---: | ---: |']
    text += [f"| {g} | {v['recorded']} | {v['joint_pass']} |" for g,v in summary['groups'].items()]
    text += ['', '配置与 Agent 哈希见 agent_freeze.json；全部输入与运行脚本哈希见 evaluation_freeze.json。',
             '逐例完整记录见 cases/；上游来源、选取决定和预检在 data/holdout100_v1/。']
    (OUT/'report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return summary


def main():
    save(OUT/'status.json',{'stage':'preparing','updated':now()})
    while not (DATA/'manifest.json').exists():
        err=OUT/'prepare6_stderr.log'
        if err.exists() and 'Traceback' in err.read_text(encoding='utf-8',errors='replace'):
            raise ValueError('Preparation failed; inspect prepare6_stderr.log, no inference started')
        time.sleep(10)
    from scripts.holdout100_audit import audit
    audit()
    agent=verify_agent()
    manifest=verify_manifest(DATA/'manifest.json');assert len(manifest['cases'])==100
    freeze_path=OUT/'evaluation_freeze.json'
    if not freeze_path.exists():
        paths=[p for p in DATA.rglob('*') if p.is_file()]
        paths += list(Path('scripts').glob('holdout100_*.py'))+[Path('docs/HOLDOUT100_PLAN.md'),OUT/'agent_freeze.json']
        save(freeze_path,{'created':now(),'sha256':fingerprint(paths),'environment':environment(),
                          'model_identity':agent['model_identity'],'policy':'Agent frozen before selection; 100 tasks sealed before any inference; once per task'})
    frozen=json.loads(freeze_path.read_text());integrity(frozen)
    config=agent['resolved_config'];model=make_model(config)
    check_runtime(model,frozen)
    probe_path=OUT/'capability_probe.json'
    if not probe_path.exists():
        model._post_json('/api/generate',{'model':model.model_name,'prompt':'','stream':False,
                                        'keep_alive':'10m','options':{'num_ctx':16384,'temperature':0}})
        probe=to_jsonable(run_probe(model,default_registry().specs,timeout_seconds=90,use_cache=False))
        save(probe_path,{'result':probe,'runtime':check_runtime(model,frozen,loaded=True)})
    if json.loads(probe_path.read_text())['result']['status']!='passed':raise ValueError('Full probe failed')
    save(OUT/'status.json',{'stage':'running','updated':now()})
    for position,case in enumerate(manifest['cases'],1):
        integrity(frozen)
        destination=OUT/'cases'/f"{case['id']}.json";started=OUT/'started'/f"{case['id']}.json"
        if destination.exists():continue
        if started.exists():raise ValueError('Interrupted attempt requires audit, not silent retry: '+case['id'])
        runtime=check_runtime(model,frozen,loaded=True)
        save(started,{'started':now(),'case_id':case['id']})
        row=evaluate_case(visible_case(case),'loop',config,make_model(config),trigger_gate=True)
        save(OUT/'visible'/f"{case['id']}.json",row)
        hidden=final_acceptance(case,row)
        row.update(hidden_acceptance=hidden,joint_pass=real_pass(row) and hidden['status']=='PASS',
                   runtime_before=runtime,source_group=case['provenance']['kind'],category=case['category'],
                   run_id='holdout100_v1',hidden_test_sha256=case['hashes']['test_hidden.py'])
        save(destination,row);integrity(frozen);report()
        print(f"{position}/100 {case['id']}: visible={row['status']} hidden={hidden['status']} joint={row['joint_pass']}",flush=True)
    summary=report();integrity(frozen)
    save(OUT/'completion.json',{'completed':now(),'integrity':'PASS','summary':summary})
    save(OUT/'status.json',{'stage':'complete','updated':now()})


if __name__=='__main__':
    try:main()
    except Exception as exc:
        save(OUT/'status.json',{'stage':'blocked','updated':now(),'error_type':type(exc).__name__,'reason':str(exc)})
        raise
