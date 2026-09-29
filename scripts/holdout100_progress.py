"""Low-cost local progress display, independent of model calls."""
import json
import re
import time
from pathlib import Path

ROOT=Path('results/holdout100_v1')


def update():
    status=json.loads((ROOT/'status.json').read_text(encoding='utf-8'))
    summary=json.loads((ROOT/'summary.json').read_text(encoding='utf-8')) if (ROOT/'summary.json').exists() else {}
    log=ROOT/'prepare6_stdout.log'
    matches=re.findall(r'Selected (\d+)',log.read_text(encoding='utf-8',errors='replace')) if log.exists() else []
    selected=int(matches[-1]) if matches else 0
    checkpoint=Path('data/holdout100_v1/selection_progress.json')
    if checkpoint.exists():
        selected=max(selected,json.loads(checkpoint.read_text(encoding='utf-8')).get('selected',0))
    if Path('data/holdout100_v1/manifest.json').exists():
        selected=100
    stage=status['stage']
    labels={'preparing':'准备及预检中','running':'正式 Agent 评估中','blocked':'已停止，需要处理','complete':'已完成'}
    text=f'''# 100 个新任务：实时进度

状态：{labels.get(stage,stage)}

| 项目 | 数量 |
| --- | ---: |
| 总目标 | 100 |
| 本轮准备合格 | {selected} |
| 正式已完成 | {summary.get('recorded',0)} |
| 可见检查通过 | {summary.get('visible_host_pass',0)} |
| 保留验收通过 | {summary.get('hidden_pass',0)} |
| 最终联合通过 | {summary.get('joint_pass',0)} |

“本轮准备合格”只表示任务有效，不是 Agent 修复成功。
最终成功数看“最终联合通过”：可见正式检查和保留验收均须通过。
本文件每 15 秒刷新一次；重新打开或刷新预览即可查看。
'''
    if status.get('reason'):text+='\n停止原因：'+status['reason']+'\n'
    (ROOT/'progress.md').write_text(text,encoding='utf-8')
    return stage


if __name__=='__main__':
    while True:
        try:
            if update() in {'complete','blocked'}:break
        except (OSError,json.JSONDecodeError):
            pass
        time.sleep(15)
