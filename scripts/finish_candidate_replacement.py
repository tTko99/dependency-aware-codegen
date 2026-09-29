"""Finish derived reporting once the frozen Agent batch completes."""
import json
import time

from scripts.report_candidate_replacement import main as report
from scripts.retest_candidate_replacement import OUT, protected


def main():
    while not (OUT/'completion.json').exists():
        time.sleep(30)
    protected()
    report()
    summary=json.loads((OUT/'summary.json').read_text())
    status=json.loads((OUT/'status.json').read_text())
    status.update(stage='complete', reason=None, formal_model_attempts=220, summary=summary)
    (OUT/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print('Reporting complete',flush=True)


if __name__ == '__main__':
    main()
