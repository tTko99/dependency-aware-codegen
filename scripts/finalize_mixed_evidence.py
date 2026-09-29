"""Correct derived mixed-source reporting for an audited unknown interruption."""
import json
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save
from scripts.finalize_external_evidence import adjust
from scripts.horizontal_report import load_rows
from scripts.horizontal_run import OUTPUT, verify


def corrected(stats, rows):
    selected = [dict(r, evaluation_cohort='selected') for r in rows]
    return adjust({'cohorts': {'selected': stats}}, selected)['cohorts']['selected']


def main():
    frozen = verify()
    rows = load_rows(frozen)
    archive = OUTPUT / 'recovery'
    for name in ('summary.json', 'report.md'):
        dest = archive / ('frozen_report_' + name)
        if not dest.exists():
            dest.write_bytes((OUTPUT / name).read_bytes())
    summary = json.loads((archive / 'frozen_report_summary.json').read_text(encoding='utf-8'))
    summary['overall_descriptive_only'] = corrected(summary['overall_descriptive_only'], rows)
    for section, key in [('by_source', 'evaluation_cohort'), ('by_category', 'category')]:
        for label, stats in summary[section].items():
            summary[section][label] = corrected(stats, [r for r in rows if r[key] == label])
    summary['interruption_reporting'] = {
        'case': 'public_split_after', 'condition': 'loop', 'retried': False,
        'policy': 'Unknown outcome retained in planned denominator; not a model failure. Unmeasured costs excluded; protocol only observed invoked runs.',
        'finalizer_sha256': sha(Path(__file__).read_bytes())}
    verification = OUTPUT / 'verification.json'
    if verification.exists():
        summary['engineering_verification'] = json.loads(verification.read_text(encoding='utf-8'))
    save(OUTPUT / 'summary.json', summary)
    text = (archive / 'frozen_report_report.md').read_text(encoding='utf-8')
    for condition, metrics in summary['overall_descriptive_only']['conditions'].items():
        new = metrics['cost_repairs']
        # Match the exact displayed table row rather than altering raw evidence.
        for line in text.splitlines():
            if line.startswith('| ' + condition + ' |'):
                replacement = f"| {condition} | {new['runs']} | {new['mean_steps']:.2f} | {new['mean_model_calls']:.2f} | {new['mean_seconds']:.2f} |"
                text = text.replace(line, replacement)
    if 'engineering_verification' in summary:
        text = text.replace(json.dumps({'status': 'not recorded'}, ensure_ascii=False, indent=2), json.dumps(summary['engineering_verification'], ensure_ascii=False, indent=2))
    note = ('## 中断审计与统计口径\n\n'
            '100次计划尝试均有记录，其中99次有完整结果、1次结果未知。'
            '`public_split_after` 的Agent进程退出后只留下启动标记，未重跑。'
            '该项保留在计划分母内，不算通过，也不归因于模型失败；耗时、调用与步骤占位值不参与成本均值，正式协议分母只含实际观测。'
            '因此“全部有记录”不等于“全部结果已知”。原始派生报告见 recovery/，原始案例证据未改动。\n\n')
    text = text.replace('## 按来源报告', note + '## 按来源报告')
    original_summary = json.loads((archive / 'frozen_report_summary.json').read_text(encoding='utf-8'))
    text = text.replace(json.dumps(original_summary['overall_descriptive_only']['paired_repair_outcomes'], indent=2), json.dumps(summary['overall_descriptive_only']['paired_repair_outcomes'], indent=2))
    overall = summary['overall_descriptive_only']
    a = overall['conditions']['one-shot']['repair_pass']['numerator']
    b = overall['conditions']['loop']['repair_pass']['numerator']
    text += (f'\n## 结论\n\n本次新增40个缺陷任务，单次修复证明通过{a}例，Agent证明通过{b}例，'
             '另有1次Agent运行中断、结果未知。人工场景与公开适配须分组解释，不能视为真实用户修复率。'
             'Agent在本批任务上的已证明通过数低于单次修复；本轮保留这一结果，不继续针对评估集调整控制逻辑或提示词。\n')
    (OUTPUT / 'report.md').write_text(text, encoding='utf-8')
    verify()
    print(json.dumps({k: {'one_shot': s['conditions']['one-shot']['repair_pass'], 'agent': s['conditions']['loop']['repair_pass'], 'rescue': s['strict_rescue']} for k,s in summary['by_source'].items()}))


if __name__ == '__main__':
    main()
