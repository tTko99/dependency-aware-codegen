"""Descriptive failure labels; does not modify scores, candidates or frozen inputs."""
import json
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save
from evaluation.interview_metrics import real_pass
from scripts.expansion200_report import load_rows
from scripts.expansion200_run import OUTPUT, verify


def main():
    frozen=verify(); rows=load_rows(frozen); items=[]
    for row in rows:
        if real_pass(row):continue
        checks=row.get('final_verification',{}).get('checks',{})
        denied=[k for k,v in checks.items() if v['status']=='denied']
        failed=[k for k,v in checks.items() if v['status']=='success' and v.get('evidence',{}).get('passed') is False]
        patches=[s for s in row.get('trajectory',[]) if (s.get('tool_call') or {}).get('name')=='apply_patch']
        labels=[]
        if row.get('measurement_status')=='interrupted_unknown':labels.append('interrupted_unknown_not_model_failure')
        if denied:labels.append('policy_refusal_not_executed')
        if failed:labels.append('executed_checks_failed')
        if patches and not any(s['tool_result']['status']=='success' for s in patches):labels.append('no_patch_accepted')
        if row['termination_reason'] in {'max_steps','global_timeout'}:labels.append('budget_exhausted')
        items.append({'case_id':row['case_id'],'condition':row['condition'],'labels':labels,
             'denied_checks':denied,'failed_checks':failed,'termination_reason':row['termination_reason'],
             'patch_errors':[s['tool_result'].get('evidence',{}).get('error_code') for s in patches if s['tool_result']['status']!='success'],
             'artifact':f"cases/{row['condition']}_{row['case_id']}.json"})
    save(OUTPUT/'failure_analysis.json',{'records_considered':len(rows),'planned_records':262,'analysis_is_posthoc':True,'nonexclusive_labels':True,'scoring_unchanged':True,'script_sha256':sha(Path(__file__).read_bytes()),'cases':items})
    lines=['# 失败与未知结果分析','','标签来自已记录的宿主证据，不改变通过率。策略拒绝不等于实际执行后证明算法错误。','','| 任务 | 策略 | 原因标签 | 失败检查 | 拒绝检查 |','| --- | --- | --- | --- | --- |']
    for r in items:lines.append(f"| {r['case_id']} | {r['condition']} | {', '.join(r['labels'])} | {', '.join(r['failed_checks'])} | {', '.join(r['denied_checks'])} |")
    (OUTPUT/'failure_analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'observed_records':len(rows),'nonpass_or_unknown':len(items)}))


if __name__=='__main__':
    main()
