# Agent contracts (M0)

The existing `run` command and `DependencyGuardPipeline` remain the one-shot baseline.
The opt-in agent uses `AgentModel.decide(messages, tools, timeout_seconds=...)` for
one decision. A decision contains one registered tool call and a short public
decision summary (`thought`); hidden reasoning is neither requested nor stored.

`ToolDispatcher` registers `ToolSpec`/handler pairs. Handlers implement capabilities,
not policy. `ToolResult.status` is success, error, denied, or mock; structured
evidence and candidate content hash accompany observations. Success means the
operation completed, not that the candidate passed (see evidence `passed`).

Host-owned `AgentState` contains candidate/original code, raw input SHA-256s,
patches, snapshots, permissions, versioned checks and caches. Model messages are
bounded projections of observations; they never constitute authority to change
permissions, input hashes, checks or files. The complete `TrajectoryStep` archive
retains raw responses/results; recent steps are projected and older steps summarized.

`AgentRunResult` separates outcome from termination: `PASS`/`FAIL` with `finish`,
`INCOMPLETE` with `max_steps`, `global_timeout`, `protocol_errors`, or `no_progress`,
and `ERROR` with backend/write/rollback errors. Only an explicit finish can end a
normal run. PASS requires host-observed, non-mock, current-version package, API,
execution and (when supplied) pytest evidence. A model's conclusion is not proof.

M1 implements orchestration; M2 adds permission, integrity and risk boundaries;
M3 adds transactional memory patches and opt-in persistence; M4 measures behavior.
Each milestone records validation and limitations in `MILESTONES.md` before the next.

## Safety boundary (M2)

All dispatches, including cached validation and finish, check host permissions and
fresh source/test SHA-256s. Initial reads require read permissions; execution needs
execute and temporary-write permission. Target-write is separate and absent by default.
Execution and reflection tools screen ASTs, imports, alias chains, constructor
receivers and resolvable getattr calls. Dynamic attribute access and untrusted
imports are conservatively refused. Supplied pytest code is screened too.

Risk modes: `reject` refuses; `mock` returns a conspicuous non-executed observation;
`requires_sandbox` refuses and declares an unmet sandbox requirement. None bypass
screening. Mock cannot establish a passed check. The trusted import set is deliberately
small; this can reject benign programs. Static Python analysis is incomplete and
cannot secure adversarial code. Dependencies themselves are trusted installation
inputs. Subprocesses, temporary directories and deadlines are process/time boundaries,
not security isolation. The preserved one-shot baseline remains for trusted inputs.

## Memory patches and persistence (M3)

Unified diffs address exactly one authorized source beneath project_root. Headers
are preferred; headerless @@ hunks require an explicit path for this unique target.
Hunks locate unique matching context in the original candidate. M6 ignores declared
line numbers/counts and normalizes both after matching. Missing/ambiguous/overlapping hunks, forbidden
paths and invalid syntax leave the whole candidate unchanged. Raw rejected diff
and an error line are returned. Successful changes invalidate checks and cache.
`rollback` restores the initial memory candidate, including across multiple patches.

The model has no disk-write tool. After verified finish, CLI `--apply` invokes
host persistence under the remaining global deadline. It checks permissions and
input hashes, saves original bytes, stages and atomically replaces the target,
then repeats actual validation/execution/tests. Failure restores original bytes;
an external concurrent modification is preserved and yields rollback_failed with
the retained snapshot. Successful completion cleans temporary snapshots. Filesystem
hash checks narrow races but are not an OS file lock against hostile concurrent writers.
Persistence diagnostics and post-write evidence are returned in `persistence`.

## Native provider protocol and evaluation (M4)

Ollama receives native `tools` definitions. Only exactly one native
`message.tool_calls` entry is an action; JSON-looking content is still text and
becomes a protocol observation. Recent messages use assistant tool calls followed
by tool observations; old steps remain summarized. The provider's optional hidden
thinking field is not requested or retained. Empty public summaries are recorded
as the observable selected tool name. Initial M1's JSON-content adapter was found
to conflict with the text-only requirement during M4, corrected, and fully rerun.

`evaluation.agent_benchmark` runs original sanity before the frozen failure cohort.
Replay never produces rescue counts. Live counts require a current attempted
one-shot failure, an actual successful patch, native finish and real non-mock
current-version validation/test evidence. Each source/test is hashed before and
after; historical LF-normalized comparisons are distinct from raw-byte integrity.
The five historical failures produced three current one-shot failures and zero
rescues. Full results, configuration and per-case trajectories are committed.

## M5 protocol and runtime extension

See [M5 contracts and verification](M5.md) for the current interfaces. `AgentDecision`
now distinguishes native tool_call, text, protocol_error and provider_error. Native
call IDs round-trip through cloud tool observations; hidden reasoning is discarded.
An isolated three-stage preflight runs before formal state mutation and does not
consume formal steps. Failure is FAIL / MODEL_TOOL_PROTOCOL_UNSUPPORTED; provider
failure leaves the native capability unknown rather than declaring it unsupported.

Finish checks host-configured required checks against both candidate and validation
context hashes. Explicit false success is recorded. Defaults retain all previous
checks. Persistence retains its stricter complete post-write checks even when a
custom formal-run configuration requires fewer checks.

Model-visible observations are bounded by serialized character count; old steps
are host summaries. Full results remain in the trajectory with JSON-pointer refs.
Repeat/cache fingerprints include normalized arguments, candidate and relevant
external context. Changed code/config, infrastructure failure, or explicit host
rerun permission allow execution retry. A repeated-call warning precedes no_progress.
M5 does not change the safety boundary or introduce a security sandbox.

## M6 lifecycle

Schema 2 identifies candidates with a monotonic revision plus a SHA-256 content hash.
Every successful memory patch or global memory rollback increments the revision,
retains in-memory history and invalidates validation evidence. Exact ordered hunk
matching is transactional, with preserved LF/CRLF and explicit EOF newline markers.
The patch tool checks real paths and its single-file write scope independently.

Final persistence rechecks the finish event, current candidate/context evidence,
source/test/config hashes, permission and regression guard. Snapshots precede only
actual writes; same-directory staged writes use flush/fsync and atomic replacement.
Rollback records attempted/succeeded/failure_reason/restored_sha256. A conflicting
external write is preserved with the recovery snapshot rather than overwritten.
Regression guard findings are heuristic: severe findings block PASS, others warn.
See [M6 evidence and limitations](M6.md). No security sandbox was added.

## Local Ollama protocol audit and paired evaluation

Ollama native calls preserve optional `id` and `function.index`. Native arguments
accept an object or a JSON-encoded object; ordinary assistant content is never
promoted into a call. Tool observations retain `role=tool`, `tool_name`, and call
association. Provider `thinking` fields are not archived.

The isolated probe now records response model, original argument type, call ID,
observation, finish arguments and termination reason. Its schema version is part
of the probe-cache identity. The evaluation disables that cache for each case.

The new local paired configuration enables `shared_initial_evidence`: both arms
receive the same bounded format of initial host diagnostics. Full diagnostics stay
in the artifact; the external state carries only the model-visible projection.
Initial successful checks are genuine versioned host evidence, and any memory
patch invalidates them. The original configurations and one-shot CLI are unchanged.

A successful external final audit does not upgrade a premature, host-rejected
finish. Strict rescue additionally requires an explicit successful native finish;
a failed first Agent repair followed by a successful second repair is insufficient
when the paired one-shot already passed. See the [30B validation report](../results/qwen3_validation/report.md)
and [reproduction and output contracts](QWEN3_LOCAL_VALIDATION.md).

## M7.2 behavior control

The public `run_agent` entry first validates the original candidate with host tools.
A fully passing original returns NO_REPAIR_NEEDED with agent_invoked=false and no
model/probe/patch calls. CLI and the M7.2 evaluator use this gate; AgentLoop.run is
the low-level continuation API for already-triggered work and isolated tests.

Successful finish is now conditional: missing, failed, stale or regression-blocked
evidence returns FINISH_PRECONDITION_FAILED to the model without terminating.
No checks are automatically scheduled in response. Unchanged repeated invalid
finishes still hit the existing repeat warning/no_progress bound. Explicit failure
or abandonment terminates with FAIL even if some checks passed.

Every observation includes a compact validation_state. Historical check records
survive memory patches as stale; authoritative passed evidence is still cleared.
The current version must independently satisfy every required check before a
success finish can terminate. Details and frozen comparison: [M7.2](M7_2.md).
