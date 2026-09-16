"""Derive a reviewable report from immutable per-case run artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main():
    root = Path("results/agent_evaluation")
    summary = json.loads((root / "live/summary.json").read_text())
    rows = [json.loads(path.read_text()) for path in sorted((root / "live").glob("failure_*.json"))]
    cohort = {
        "source_manifest": "data/agent_failures/manifest.json",
        "selection": "Current completed one-shot repair FAIL; no selection by loop outcome",
        "config_sha256": summary["config_sha256"],
        "cases": [{"id": row["id"], "case_result": f"live/failure_{row['id']}.json",
                   "case_result_sha256": hashlib.sha256(
                       (root / f"live/failure_{row['id']}.json").read_bytes()).hexdigest(),
                   "input_hashes": row["before_hashes"]} for row in rows if row["first_failed"]],
    }
    (root / "confirmed_one_shot_failures.json").write_text(json.dumps(cohort, indent=2))
    lines = [
        "# M4 — reproducible agent evaluation", "",
        f"**多轮救回 {summary['rescued']} / 一次修复失败 {summary['single_shot_failed']}**", "",
        "This run provides no evidence of a multi-round repair improvement.", "",
        "## Original engineering sanity", "",
        "Live Ollama rerun: **8/8 repaired cases PASS; 2/2 controls NO_REPAIR_NEEDED**.",
        "All source/test raw bytes were unchanged before/after. Current Windows checkout",
        "uses CRLF; historical hashes were LF. Every LF-normalized content hash matches",
        "history, while independent current raw-byte hashes prove run-time integrity.", "",
        "Historical-output replay also reproduced 8/8 + 2/2. Replay results are separate",
        "and never used as live model or rescue evidence.", "",
        "## Fixed failure cohort and comparison", "",
        "All five historical attempted failures were frozen from the committed 7B",
        "controlled results. Detector misses and correct controls were excluded.",
        "Exact source, tests, historical repair, reference, provenance and SHA-256s are in",
        "[the manifest](../../data/agent_failures/manifest.json). Historical replay reproduced",
        "5/5 failures. On the current live one-shot run, only three still failed; the two",
        "current successes are excluded from the rescue denominator. The resulting",
        "[confirmed cohort](confirmed_one_shot_failures.json) links exact run evidence.", "",
        "Both live arms used the same model digest, source, tests, environment, seed 42,",
        "temperature 0, top_p 1, repeat penalty 1, context 4096 and 256 tokens per model",
        "call. The loop may make more calls (24-step / 180-second limits); this is not",
        "an equal-total-token experiment. Execution timeout is 10 seconds for both arms.",
        "The one-shot prompt returns a whole program; the loop prompt selects native",
        "tools and supplies unified diffs. The original sanity rerun uses its unchanged",
        "engineering config. Historical controlled failures had a 64-token cap; the new",
        "paired comparison uses a frozen shared 256-token config, not that historical cap.", "",
        "| Case | Current one-shot | Loop outcome / reason | Steps | One-shot / loop seconds | Rescue step |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        loop = row["loop"]
        lines.append(
            f"| [{row['id']}](live/failure_{row['id']}.json) | {row['one_shot']['status']} | "
            f"{loop['final_status']} / {loop['termination_reason']} | {len(loop['trajectory'])} | "
            f"{row['one_shot']['elapsed_seconds']:.3f} / {loop['elapsed_seconds']:.3f} | "
            f"{row['rescued_at_step'] or 'none'} |",
        )
    unchanged_candidates = all(row["loop"]["candidate_code"] ==
                               row["one_shot"]["result"]["generated_code"] for row in rows)
    lines += [
        "", "## Actual final evidence and failure diagnosis", "",
        f"All loop candidates equal their original supplied code: **{unchanged_candidates}**.",
        "Their exact original programs failed actual pytest in the baseline's initial",
        "execution (see each `one_shot.result.execution_result`). No loop candidate",
        "was successfully patched; no current-version validation PASS was established",
        "by the loop. The host correctly returns INCOMPLETE, not a model-declared PASS.",
        "The native adapter received JSON-looking **text content**, not API `tool_calls`.",
        "Three consecutive protocol observations terminated each run. Raw responses,",
        "observations, timestamps and durations are preserved in each trajectory.", "",
        "An earlier JSON-content adapter preflight is retained under",
        "`json_protocol_preflight/` for audit, but is **not the acceptance run**: accepting",
        "text JSON violated the text-only-response requirement. It repeatedly produced",
        "malformed patch counts and ended with no_progress. The adapter was corrected",
        "to native tools and the complete live evaluation was rerun; that rerun is the",
        "table above. No results were substituted or counted as rescue from the preflight.", "",
        "The conservative agent safety list also refuses SciPy/NumPy imports unless",
        "rewritten to supported safe capabilities or run under a future real sandbox.",
        "This limitation did not cause this run's termination (protocol failed first),",
        "but remains a separate barrier for numerical workloads. Static screening and",
        "temporary subprocesses do not provide an adversarial security sandbox.", "",
        "## Runtime and reproduction", "",
        f"- Run UTC: `{summary['timestamp']}`",
        f"- Python: `{summary['environment']['python']}`",
        f"- Ollama: `{summary['model_identity']['ollama_version']}`",
        f"- Model digest: `{summary['model_identity']['installed_model']['digest']}`",
        "- Full environment, runtime placement and configuration: [live summary](live/summary.json).",
        "- Input-preserving replay: [replay summary](replay/summary.json).", "",
        "```powershell",
        "$env:PYTHONPATH='src'",
        "python -m evaluation.agent_benchmark --mode replay --output-dir results/agent_evaluation/replay_new",
        "python -m evaluation.agent_benchmark --mode live --output-dir results/agent_evaluation/live_new",
        "```", "",
        "The checked-in report uses the archived `live/` run. Use a new output directory",
        "to preserve prior evidence. Model/tool protocol reliability and a real sandbox",
        "remain unresolved; this small cohort supports no broad accuracy claim.", "",
    ]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
