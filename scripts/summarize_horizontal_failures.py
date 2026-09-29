"""Post-hoc descriptive labels from raw evidence; never changes frozen scores."""

from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save
from evaluation.interview_metrics import real_pass
from scripts.horizontal_report import load_rows
from scripts.horizontal_run import OUTPUT, verify


def main():
    frozen = verify()
    rows = load_rows(frozen)
    analyses = []
    for row in rows:
        if real_pass(row):
            continue
        checks = row.get("final_verification", {}).get("checks", {})
        denied = {
            name: value.get("evidence", {}).get("findings", [])
            for name, value in checks.items()
            if value["status"] == "denied"
        }
        failed = [
            name
            for name, value in checks.items()
            if value["status"] == "success" and value.get("evidence", {}).get("passed") is False
        ]
        patches = [
            s
            for s in row.get("trajectory", [])
            if (s.get("tool_call") or {}).get("name") == "apply_patch"
        ]
        labels = []
        if row.get("measurement_status") == "interrupted_unknown":
            labels.append("external_interruption_unknown_not_model_failure")
        if denied:
            labels.append("policy_refusal_not_executed")
        if failed:
            labels.append("executed_checks_failed")
        if patches and not any(s["tool_result"]["status"] == "success" for s in patches):
            labels.append("no_patch_accepted")
        if row["termination_reason"] in {"max_steps", "global_timeout"}:
            labels.append("budget_exhausted")
        analyses.append(
            {
                "case_id": row["case_id"],
                "condition": row["condition"],
                "source_group": row["evaluation_cohort"],
                "status": row["status"],
                "termination_reason": row["termination_reason"],
                "labels": labels,
                "denied_checks": denied,
                "failed_checks": failed,
                "patch_errors": [
                    s["tool_result"].get("evidence", {}).get("error_code")
                    for s in patches
                    if s["tool_result"]["status"] != "success"
                ],
                "evidence_file": f"cases/{row['condition']}_{row['case_id']}.json",
            }
        )
    save(
        OUTPUT / "failure_analysis.json",
        {
            "method": "Post-hoc nonexclusive labels; no score changes",
            "freeze_id": frozen["freeze_id"],
            "analysis_script_sha256": sha(Path(__file__).read_bytes()),
            "cases": analyses,
        },
    )
    lines = [
        "# 失败原因补充分析",
        "",
        "本表从已完成的原始证据提取非互斥标签，不改变冻结指标或通过率。",
        "策略拒绝意味着相应候选没有被允许执行，不等于运行测试后证明算法错误。",
        "没有成功应用补丁时，失败的正式检查可能仍对应原始错误代码。",
        "",
        "| 任务 | 条件 | 原因标签 | 失败检查 | 被拒绝检查 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in analyses:
        lines.append(
            f"| {item['case_id']} | {item['condition']} | {', '.join(item['labels'])} | "
            f"{', '.join(item['failed_checks'])} | {', '.join(item['denied_checks'])} |"
        )
    lines += [
        "",
        "具体规则发现、补丁错误和原始记录路径见failure_analysis.json。",
        "解释笔记见review_notes.md；所有候选、正式验证和原始工具轨迹均保留。",
    ]
    (OUTPUT / "failure_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = OUTPUT / "report.md"
    original = report.read_text(encoding="utf-8")
    if "[失败原因补充分析]" not in original:
        report.write_text(
            original + "\n[失败原因补充分析](failure_analysis.md) · [逐例解释](review_notes.md)\n",
            encoding="utf-8",
        )
    save(
        OUTPUT / "artifact_inventory.json",
        {
            p.relative_to(OUTPUT).as_posix(): sha(p.read_bytes())
            for p in sorted(OUTPUT.rglob("*"))
            if p.is_file() and p.name != "artifact_inventory.json"
        },
    )
    print(f"Annotated {len(analyses)} non-passing attempts without changing scores")


if __name__ == "__main__":
    main()
