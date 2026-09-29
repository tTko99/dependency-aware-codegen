"""Record post-run engineering checks without modifying frozen evaluation inputs."""
import os
import re
import subprocess
import sys
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import now, save
from scripts.horizontal_run import OUTPUT, verify


def main():
    verify()
    env = dict(os.environ, PYTHONPATH='src;.')
    commands = {
        'pytest': [sys.executable, '-m', 'pytest', '-ra'],
        'reporting_tests': [sys.executable, '-m', 'pytest', 'scripts/horizontal_tests.py',
                            'scripts/test_external_reporting_recovery.py',
                            'scripts/test_mixed_reporting_recovery.py', '-ra'],
        'ruff': [sys.executable, '-m', 'ruff', 'check', '--no-cache', '.'],
    }
    checks = {}
    for name, cmd in commands.items():
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        (OUTPUT / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        checks[name] = {'exit_code': result.returncode, 'log': name + '.log',
                        'summary': result.stdout.strip().splitlines()[-3:]}
        print(name, result.returncode, checks[name]['summary'], flush=True)
    patterns = [r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
                r'\bsk-[A-Za-z0-9]{24,}', r'\bgh[pousr]_[A-Za-z0-9]{30,}']
    matches = []
    for root in [Path('data/horizontal_eval_v1'), OUTPUT]:
        for p in root.rglob('*'):
            if p.is_file() and p.suffix in {'.json', '.jsonl', '.md', '.txt', '.log'}:
                text = p.read_text(encoding='utf-8', errors='replace')
                if any(re.search(pattern, text) for pattern in patterns):
                    matches.append(p.as_posix())
    verify()
    save(OUTPUT / 'verification.json', {'verified_at': now(), 'checks': checks,
         'frozen_inputs_implementation_and_prior_results_unchanged': True,
         'secret_pattern_scan': {'matches': matches, 'scope': 'new data and output text; heuristic, not exhaustive'},
         'verification_script_sha256': sha(Path(__file__).read_bytes())})
    if matches or any(c['exit_code'] for c in checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
