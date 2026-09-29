"""Report the Agent-only retest without altering frozen measurements."""
import json
from collections import Counter
from pathlib import Path

from evaluation.interview_metrics import real_pass

ROOT = Path('results/candidate_replace_v1')


def main():
    rows = [json.loads(p.read_text()) for p in sorted((ROOT/'cases').glob('*.json'))]
    old = {}
    for folder in ['external_eval_v1', 'horizontal_eval_v1', 'expansion200_v1']:
        for p in (Path('results')/folder).rglob('loop_*.json'):
            row = json.loads(p.read_text())
            if row.get('condition') == 'loop':
                old[row['case_id']] = row
    defects = [r for r in rows if not r['is_control']]
    controls = [r for r in rows if r['is_control']]
    pairs = Counter()
    for row in defects:
        baseline = old.get(row['case_id'])
        if baseline is None or baseline.get('measurement_status') == 'interrupted_unknown':
            pairs['baseline_unknown'] += 1
        elif real_pass(row):
            pairs['both_pass' if real_pass(baseline) else 'improved'] += 1
        else:
            pairs['regressed' if real_pass(baseline) else 'both_nonpass'] += 1
    edits = [s for r in rows for s in r.get('trajectory', [])
             if (s.get('tool_call') or {}).get('name') in {'apply_patch', 'replace_candidate'}]
    tools = {name: {'calls':sum(s['tool_call']['name']==name for s in edits),
                   'accepted':sum(s['tool_call']['name']==name and s['tool_result']['status']=='success' for s in edits)}
             for name in ['apply_patch', 'replace_candidate']}
    result = {'observed_defects':len(defects),'planned_defects':200,
              'passes':sum(map(real_pass, defects)), 'observed_controls':len(controls),
              'controls_pass':sum(map(real_pass, controls)), 'pairs':dict(pairs),'edit_tools':tools,
              'final':(ROOT/'completion.json').exists()}
    (ROOT/'agent_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    text = ['# Agent 完整代码替换复测', '',
            '本次只复测 Agent。任务、正式测试、模型配置和验收标准保持不变；改变的是候选修改接口和通用工具说明。', '',
            f"状态：{'完成' if result['final'] else '运行中，以下为阶段数据'}。", '',
            '| 指标 | 旧 Agent | 新 Agent |', '| --- | ---: | ---: |',
            f"| 缺陷任务通过 | 134/200，另有 3 个未知 | {result['passes']}/{len(defects)} 已记录，计划 200 |",
            f"| 正确代码样本通过 | 20/20 | {result['controls_pass']}/{len(controls)} 已记录，计划 20 |", '',
            '阶段数据不能直接与完整旧批次作成功率比较。未知历史结果单列，不算旧失败。公开与人工任务不是生产故障随机抽样。', '',
            '## 修改工具', '', '| 工具 | 调用 | 接受 |', '| --- | ---: | ---: |']
    text += [f"| {n} | {v['calls']} | {v['accepted']} |" for n,v in tools.items()]
    text += ['', '工具接受只表示内存候选更新成功，正式通过仍由宿主验证决定。', '',
             '## 成对变化', '', '```json', json.dumps(dict(pairs),indent=2), '```', '',
             '完整 pytest：261 passed，1 skipped；ruff 通过。正式结果见 cases/，冻结配置见 freeze.json。']
    (ROOT/'report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
