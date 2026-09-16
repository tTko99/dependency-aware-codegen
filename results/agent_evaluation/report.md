# M4 — reproducible agent evaluation

**多轮救回 0 / 一次修复失败 3**

This run provides no evidence of a multi-round repair improvement.

## Original engineering sanity

Live Ollama rerun: **8/8 repaired cases PASS; 2/2 controls NO_REPAIR_NEEDED**.
All source/test raw bytes were unchanged before/after. Current Windows checkout
uses CRLF; historical hashes were LF. Every LF-normalized content hash matches
history, while independent current raw-byte hashes prove run-time integrity.

Historical-output replay also reproduced 8/8 + 2/2. Replay results are separate
and never used as live model or rescue evidence.

## Fixed failure cohort and comparison

All five historical attempted failures were frozen from the committed 7B
controlled results. Detector misses and correct controls were excluded.
Exact source, tests, historical repair, reference, provenance and SHA-256s are in
[the manifest](../../data/agent_failures/manifest.json). Historical replay reproduced
5/5 failures. On the current live one-shot run, only three still failed; the two
current successes are excluded from the rescue denominator. The resulting
[confirmed cohort](confirmed_one_shot_failures.json) links exact run evidence.

Both live arms used the same model digest, source, tests, environment, seed 42,
temperature 0, top_p 1, repeat penalty 1, context 4096 and 256 tokens per model
call. The loop may make more calls (24-step / 180-second limits); this is not
an equal-total-token experiment. Execution timeout is 10 seconds for both arms.
The one-shot prompt returns a whole program; the loop prompt selects native
tools and supplies unified diffs. The original sanity rerun uses its unchanged
engineering config. Historical controlled failures had a 64-token cap; the new
paired comparison uses a frozen shared 256-token config, not that historical cap.

| Case | Current one-shot | Loop outcome / reason | Steps | One-shot / loop seconds | Rescue step |
| --- | --- | --- | ---: | ---: | --- |
| [argc_json_decoder_v06](live/failure_argc_json_decoder_v06.json) | FAIL | INCOMPLETE / protocol_errors | 3 | 6.969 / 3.563 | none |
| [class_fractions_fraction_v01](live/failure_class_fractions_fraction_v01.json) | FAIL | INCOMPLETE / protocol_errors | 3 | 1.156 / 2.110 | none |
| [func_scipy_softmax_v03](live/failure_func_scipy_softmax_v03.json) | PASS | INCOMPLETE / protocol_errors | 3 | 1.985 / 3.594 | none |
| [func_scipy_softmax_v04](live/failure_func_scipy_softmax_v04.json) | PASS | INCOMPLETE / protocol_errors | 3 | 1.687 / 3.594 | none |
| [func_scipy_softmax_v07](live/failure_func_scipy_softmax_v07.json) | FAIL | INCOMPLETE / protocol_errors | 3 | 1.594 / 3.578 | none |

## Actual final evidence and failure diagnosis

All loop candidates equal their original supplied code: **True**.
Their exact original programs failed actual pytest in the baseline's initial
execution (see each `one_shot.result.execution_result`). No loop candidate
was successfully patched; no current-version validation PASS was established
by the loop. The host correctly returns INCOMPLETE, not a model-declared PASS.
The native adapter received JSON-looking **text content**, not API `tool_calls`.
Three consecutive protocol observations terminated each run. Raw responses,
observations, timestamps and durations are preserved in each trajectory.

An earlier JSON-content adapter preflight is retained under
`json_protocol_preflight/` for audit, but is **not the acceptance run**: accepting
text JSON violated the text-only-response requirement. It repeatedly produced
malformed patch counts and ended with no_progress. The adapter was corrected
to native tools and the complete live evaluation was rerun; that rerun is the
table above. No results were substituted or counted as rescue from the preflight.

The conservative agent safety list also refuses SciPy/NumPy imports unless
rewritten to supported safe capabilities or run under a future real sandbox.
This limitation did not cause this run's termination (protocol failed first),
but remains a separate barrier for numerical workloads. Static screening and
temporary subprocesses do not provide an adversarial security sandbox.

## Runtime and reproduction

- Run UTC: `2026-09-15T22:06:35.647450+00:00`
- Python: `3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]`
- Ollama: `0.34.1`
- Model digest: `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`
- Full environment, runtime placement and configuration: [live summary](live/summary.json).
- Input-preserving replay: [replay summary](replay/summary.json).

```powershell
$env:PYTHONPATH='src'
python -m evaluation.agent_benchmark --mode replay --output-dir results/agent_evaluation/replay_new
python -m evaluation.agent_benchmark --mode live --output-dir results/agent_evaluation/live_new
```

The checked-in report uses the archived `live/` run. Use a new output directory
to preserve prior evidence. Model/tool protocol reliability and a real sandbox
remain unresolved; this small cohort supports no broad accuracy claim.
