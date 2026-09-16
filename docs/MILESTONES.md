# Milestone review log

## M0 — contracts

- Added independent typed agent contracts, including status/termination separation,
  versioned evidence, tool registry/dispatcher and model decision interfaces.
- Kept all baseline code unchanged. Public `thought` is an observable summary.
- Validation: `python -m pytest`: **37 passed** (35 baseline + 2 contract tests).
  Targeted ruff and `git diff --check`: passed.
- Environment: project-local Python 3.12 virtualenv; pytest 9.1.1, ruff 0.16.7.
- Resolved contract issue: dynamic API reflection is executable behavior and must
  enter the M2 safety boundary, even for validation tools.
- Outstanding by design: M1–M4 implementation and live model availability.

## M1 — observation-driven state machine

- Added tool registration, argument validation, exception observations, protocol
  recovery/termination, evidence-based finish, caching and no-progress limits.
- A spawned worker bounds each model/tool call with one shared deadline; late
  state is discarded and the worker process tree is terminated. This is a timeout
  boundary, not a security sandbox. Providers/handlers must be spawn-picklable.
- Added Ollama JSON single-action adapter (no native tool support required).
  Context retains recent steps, aggregates older ones and clips model-visible
  strings; raw results remain in the returned trajectory.
- Validation: **44 pytest tests passed**, targeted ruff and diff check passed.
  Includes arbitrary action order, false PASS claims, protocol recovery, cache,
  repeated calls, exceptions, model/tool deadlines and raw-context preservation.
- Outstanding: patch tool deliberately returns a denied observation until M3;
  safety enforcement follows in M2. Live Ollama evaluation remains unverified.

## M2 — tool safety boundary

- Enforced explicit permissions and fresh raw-byte input hashes before every
  dispatch, including cache hits and finish. Input initialization hashes the bytes
  actually decoded. Added conservative AST/import screening for both candidate and tests.
- Covered dangerous aliases, indirect calls, subprocess/os/shutil, eval/exec,
  network/file operations, dunder access and unresolved dynamic attributes.
- Reject, conspicuous non-executing mock and requires_sandbox observations are
  distinct; no mode executes a risky candidate. Existing executor documentation
  now explicitly states it is not a security sandbox.
- Validation: **64 pytest tests passed**, targeted ruff and diff check passed.
- Limitations: conservative trusted-module list may reject harmless programs;
  static screening cannot establish adversarial-code safety. Legacy baseline is
  intentionally retained for trusted input. No external sandbox is configured.

## M3 — transactional patches and opt-in commit

- Implemented unique-context, all-or-nothing unified diffs, single-target headerless
  fallback, path authorization, immediate syntax checks and raw parse diagnostics.
- Added memory rollback and CLI `agent`; default dry-run, explicit --apply only
  after evidence-based finish. Snapshot, atomic write, actual postchecks, rollback
  results and successful snapshot cleanup are covered by tests.
- Resolved conflict policy: never overwrite an external concurrent edit during
  rollback; retain snapshot and report rollback_failed for manual recovery.
- Validation: **83 pytest tests passed**, targeted ruff and diff check passed.
  CLI tests perform real subprocess/pytest validation with a scripted test model;
  these are infrastructure tests and are not counted as model rescue evidence.
- Added independent execution-repeat tracking so changing arguments cannot bypass
  the host rerun permission. Updated English/Chinese CLI and architecture docs.
- Outstanding: M4 live regression/evaluation; cross-process hostile-write races
  still need OS isolation/locking. No safety-sandbox claim is made.

## M4 — live measurements and final verification

- User installed Ollama and the exact qwen2.5-coder:7b tag; installed digest matches
  history. Current runtime is Ollama 0.34.1, Python 3.12.14, GPU placement; full
  environment and configuration are preserved in the live summary.
- Original live engineering sanity: **8/8 repaired PASS, 2/2 controls preserved**.
  Current source/test raw bytes stayed unchanged. Historical hashes use LF while
  this checkout uses CRLF; both raw before/after and LF-normalized comparisons
  are reported separately, without editing frozen original inputs.
- Froze all five historical attempted failures with source, tests, historical
  candidate, reference, provenance and hashes. Replay reproduced 5/5 failures.
  Current paired run had three one-shot failures, two one-shot successes.
- **多轮救回 0 / 一次修复失败 3**. Each loop ended with protocol_errors after three
  text-only responses; no patch, mock or claimed success was counted as rescue.
  Report: `results/agent_evaluation/report.md`; case-level raw traces are included.
- Contract correction discovered in evaluation: M1's text-JSON adapter violated
  the text-only response rule. Replaced with native Ollama tools/tool_calls and
  assistant/tool observations, added regression tests, archived the preflight,
  then reran the entire live comparison. No hidden thinking field is stored.
- Other verification fixes: per-execution timeout matches the baseline (10s),
  input checks also run inside execution handlers, worker exits become tool
  observations, timeout output bytes serialize as text, post-write failure evidence
  and external-write rollback conflicts are preserved.
- Final validation: **90 pytest tests passed**, repository-wide `ruff check .`
  and `git diff --check` passed. Frozen intentional-defect fixtures are excluded
  from lint rewrites; hash tests cover their integrity instead.
- Remaining issues: the selected model's native tool protocol is unreliable in
  this run; no multi-round quality gain is demonstrated. Conservative safety
  screening does not support SciPy/NumPy execution without a future sandbox or
  supported safe rewrite. Process boundaries are not security sandboxes. The
  evaluation cohort is small and no general accuracy claim is made.
- Final staged-artifact check exposed CRLF-as-trailing-whitespace diagnostics in
  byte-preserved JSON. Added Git whitespace attributes recognizing CRLF while
  retaining trailing-space checks; artifact bytes/hashes remain unchanged.
  Full milestone-range diff check then passed.
