"""One-off completion: wait for frozen records, verify, report, and update overview."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import now, save
from scripts.expansion200_run import OUTPUT, verify


def stop_owned_service():
    metadata = OUTPUT / "owned_service.json"
    if not metadata.exists():
        return
    command = r"""
$meta=Get-Content -LiteralPath 'results/expansion200_v1/owned_service.json' -Raw | ConvertFrom-Json
$owner=Get-Process -Id $meta.pid -ErrorAction SilentlyContinue
if ($owner -and $owner.ProcessName -eq 'ollama' -and $owner.StartTime.ToUniversalTime().ToString('o') -eq $meta.started_utc) {
    $known=@([int]$meta.pid)
    $processes=Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId
    do {
        $next=@($processes | Where-Object {$_.ParentProcessId -in $known -and $_.ProcessId -notin $known} | ForEach-Object {[int]$_.ProcessId})
        $known += $next
    } while ($next.Count -gt 0)
    [array]::Reverse($known)
    foreach ($ownedId in $known) { Stop-Process -Id $ownedId -ErrorAction SilentlyContinue }
}
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    redactions = {}
    for name in ["ollama_resume_stdout.log", "ollama_resume_stderr.log"]:
        path = OUTPUT / name
        if not path.exists():
            continue
        before = path.read_bytes()
        text = before.decode("utf-8", errors="replace")
        lines = text.splitlines()
        count = sum("env=" in line for line in lines)
        if count:
            path.write_text(
                "\n".join(
                    "[Startup environment omitted]" if "env=" in line else line for line in lines
                )
                + "\n",
                encoding="utf-8",
            )
        redactions[name] = {
            "startup_environment_lines_omitted": count,
            "before_sha256": sha(before),
            "after_sha256": sha(path.read_bytes()),
        }
    save(OUTPUT / "operational_log_redactions.json", redactions)


def overview(summary):
    external = json.loads(
        Path("results/external_eval_v1/summary.json").read_text(encoding="utf-8")
    )["cohorts"]["external"]
    mixed = json.loads(Path("results/horizontal_eval_v1/summary.json").read_text(encoding="utf-8"))[
        "by_source"
    ]
    groups = [
        ("QuixBugs 公开算法缺陷", "QuixBugs public algorithm defects", external),
        ("公开库缺陷适配", "Public library defect adaptations", mixed["public_defect_adaptation"]),
        (
            "HumanEvalPack 公开人工缺陷",
            "HumanEvalPack public authored bugs",
            summary["by_source"]["public_authored_bug_benchmark"],
        ),
        ("人工综合场景", "Authored general scenarios", mixed["authored_scenario"]),
        ("人工 API 场景", "Authored API scenarios", summary["by_source"]["authored_api_scenario"]),
    ]
    for name, english, begin, end in [
        ("README_CN.md", False, "## 外部任务评估", "## 历史 Agent 评估"),
        ("README.md", True, "## External", "## Historical"),
    ]:
        path = Path(name)
        text = path.read_text(encoding="utf-8")
        header = (
            "## Evaluation: 200 single-file defect tasks"
            if english
            else "## 评估：200 个单文件缺陷任务"
        )
        if header in text:
            start = text.index(header)
        else:
            start = text.index(begin)
        stop = text.index(end, start)
        if english:
            lines = [
                header,
                "",
                "The same local Qwen3-Coder 30B was evaluated with one-shot repair and Agent tools on **200 frozen defect tasks**. Correct-code samples are excluded from this count. Sources, inputs, tests and configurations are recorded; every outcome, including interruptions, is retained.",
                "",
                "| Source | Defects | One-shot passes | Agent passes | Agent outcomes unknown |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        else:
            lines = [
                header,
                "",
                "使用同一本地 Qwen3-Coder 30B，在 **200 个冻结的单文件缺陷任务**上比较单次修复与 Agent；正确代码样本不计入此数量。记录来源、输入、测试和配置，保留失败及中断结果。",
                "",
                "| 来源 | 缺陷任务 | 单次修复通过 | Agent 通过 | Agent 中断未知 |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        for cn, en, stats in groups:
            a = stats["conditions"]["one-shot"]
            b = stats["conditions"]["loop"]
            lines.append(
                f"| {en if english else cn} | {stats['repair_cases']} | {a['repair_pass']['numerator']} | {b['repair_pass']['numerator']} | {b.get('unknown_cost_attempts', 0)} |"
            )
        if english:
            lines += [
                "",
                "HumanEvalPack contains human-inserted bugs, not production incidents. Project-authored tasks are also synthetic. Public benchmarks may appear in training data; formal tests were visible, with no independent hidden-test or human-acceptance measurement. These groups are not pooled into a production success rate.",
                "The Agent is not assumed to outperform one-shot repair. Reports retain paired outcomes, strict multi-round rescues, patch rejection reasons and measured costs. Twenty related correct-code samples in the earlier batches remained unchanged; they are separate from the 200 defects.",
                "",
                "[Complete task index](results/expansion200_v1/coverage_200.json) · [131-task extension report](results/expansion200_v1/report.md) · [Statistics](results/expansion200_v1/summary.json) · [Earlier public benchmark](results/external_eval_v1/report.md) · [Earlier mixed-source report](results/horizontal_eval_v1/report.md) · [Method](docs/EVALUATION_200_PLAN.md)",
                "",
            ]
        else:
            lines += [
                "",
                "HumanEvalPack 的错误由人工植入，不是真实生产故障；项目编写的场景也明确标注为人工来源。公开基准可能进入预训练，正式测试对模型可见，尚未测量独立隐藏测试或人工接受率，因此不把这些来源合并成生产修复率。",
                "不预设 Agent 优于单次修复；报告保留配对结果、严格多轮救回、补丁拒绝原因和实际成本。前两批另有 20 个相关正确代码样本全部保持不变，未计入 200 个缺陷任务。",
                "",
                "[完整任务索引](results/expansion200_v1/coverage_200.json) · [131例扩展报告](results/expansion200_v1/report.md) · [机器可读统计](results/expansion200_v1/summary.json) · [早期公开基准](results/external_eval_v1/report.md) · [早期混合来源报告](results/horizontal_eval_v1/report.md) · [评估方法](docs/EVALUATION_200_PLAN.md)",
                "",
            ]
        replacement = "\n".join(lines) + "\n"
        save_path = OUTPUT / "readme_before_completion" / name
        if not save_path.exists():
            save_path.parent.mkdir(exist_ok=True)
            save_path.write_bytes(path.read_bytes())
        path.write_text(text[:start] + replacement + text[stop:], encoding="utf-8")


def main(wait=False):
    if (OUTPUT / "completion.json").exists():
        print("Already completed")
        return
    while True:
        path = OUTPUT / "run_manifest.json"
        try:
            index = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            if not wait:
                raise
            time.sleep(1)
            continue
        ready = (
            len(index.get("artifact_hashes", {})) == 262
            and (OUTPUT / "integrity_final.json").exists()
        )
        if ready:
            break
        if not wait:
            raise RuntimeError("Benchmark not complete")
        time.sleep(10)
    verify()
    stop_owned_service()
    for module in [
        "scripts.verify_200_evidence",
        "scripts.expansion200_report",
        "scripts.analyze_200_evidence",
    ]:
        subprocess.run([sys.executable, "-m", module], check=True)
    summary = json.loads((OUTPUT / "summary.json").read_text(encoding="utf-8"))
    overview(summary)
    index_path = OUTPUT / "coverage_200.json"
    coverage = json.loads(index_path.read_text(encoding="utf-8"))
    coverage["not_a_claim_all_evaluation_finished"] = False
    coverage["all_planned_attempts_completed_or_audited"] = True
    coverage["unknown_results_are_not_demonstrated_passes"] = True
    save(index_path, coverage)
    verify()
    save(
        OUTPUT / "completion.json",
        {
            "completed_at": now(),
            "planned_defects": 131,
            "recorded_attempts": 262,
            "observed_attempts": summary["overall_descriptive_only"]["observed_attempts"],
            "unknown_attempts": summary["overall_descriptive_only"]["interrupted_attempts"],
            "cumulative_defect_tasks": 200,
            "frozen_inputs_and_previous_results_unchanged": True,
            "completion_script_sha256": sha(Path(__file__).read_bytes()),
        },
    )
    save(
        OUTPUT / "artifact_inventory.json",
        {
            p.relative_to(OUTPUT).as_posix(): sha(p.read_bytes())
            for p in sorted(OUTPUT.rglob("*"))
            if p.is_file()
            and p.name
            not in {"artifact_inventory.json", "completion_stdout.log", "completion_stderr.log"}
        },
    )
    print("Evaluation, checks, reports and both README updates complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    try:
        main(args.wait)
    except Exception as exc:
        save(
            OUTPUT / "completion_error.json",
            {"time": now(), "type": type(exc).__name__, "message": str(exc)},
        )
        raise
