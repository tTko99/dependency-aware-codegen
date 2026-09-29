"""Report the entire extension, retaining all outcomes and provenance groups."""

import json

from evaluation.agent_benchmark import sha
from evaluation.external_report import aggregate, fraction, trajectory
from evaluation.interview_benchmark import save, verify_manifest
from evaluation.interview_metrics import real_pass
from scripts.expansion200_prepare import DATA
from scripts.expansion200_run import OUTPUT, verify
from scripts.finalize_mixed_evidence import corrected


def load_rows(frozen):
    index = json.loads((OUTPUT / "run_manifest.json").read_text(encoding="utf-8"))
    assert index["freeze_id"] == frozen["freeze_id"]
    rows = []
    for name, digest in index["artifact_hashes"].items():
        raw = (OUTPUT / "cases" / name).read_bytes()
        assert sha(raw) == digest
        row = json.loads(raw)
        assert row["comparison_identity"] == frozen["freeze_id"]
        rows.append(row)
    return rows


def report():
    frozen = verify()
    cases = verify_manifest(DATA / "manifest.json")["cases"]
    rows = load_rows(frozen)

    def stats(selected):
        ids = {c["id"] for c in selected}
        subset = [r for r in rows if r["case_id"] in ids]
        return corrected(aggregate(selected, subset), subset)

    summary = {
        "freeze_id": frozen["freeze_id"],
        "model_identity": frozen["model_identity"],
        "overall_descriptive_only": stats(cases),
        "by_source": {},
        "by_category": {},
        "cumulative_task_count": 200,
        "historical_defect_tasks": 69,
        "extension_defect_tasks": 131,
        "cumulative_count_is_not_a_pooled_production_rate": True,
    }
    for section, key in [
        ("by_source", lambda c: c["provenance"]["kind"]),
        ("by_category", lambda c: c["category"]),
    ]:
        for label in sorted({key(c) for c in cases}):
            summary[section][label] = stats([c for c in cases if key(c) == label])
    verification = OUTPUT / "verification.json"
    if verification.exists():
        summary["engineering_verification"] = json.loads(verification.read_text(encoding="utf-8"))
    save(OUTPUT / "summary.json", summary)
    (OUTPUT / "cases.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    overall = summary["overall_descriptive_only"]
    lines = [
        "# 200任务扩展：131个冻结缺陷任务的同模型评估",
        "",
        "保留既有69个任务及全部历史结果，本批包含100个HumanEvalPack公开人工缺陷任务、31个项目编写的API场景。",
        "HumanEvalPack是人工植入错误的公开基准，不是真实生产故障，也不是本模型自然生成错误的抽样。",
        "原上游断言保持不变，加入pytest入口并固定随机种子42；本地API场景明确标注人工来源。",
        "Agent、提示词、风险规则、补丁实现、模型配置和指标不变。正式测试可见，不发送参考答案；没有隐藏测试或人工接受率。",
        "公共基准可能进入预训练；筛选受既有单文件和风险边界限制。两种策略总调用/token预算不同。",
        "",
        "## 完整性",
        "",
        f"计划尝试262次，当前有记录{len(rows)}次；结果已知{overall['observed_attempts']}次；全部结果已知：{overall['fully_observed']}。",
        "中断未知保留计划分母，不算模型失败；未知成本不以零参与均值。已开始任务不重跑，未根据模型结果挑选案例。",
        "",
        "## 按来源",
        "",
        "| 来源 | 缺陷数 | 单次修复 | Agent | 严格多轮救回 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for group, s in summary["by_source"].items():
        lines.append(
            f"| {group} | {s['repair_cases']} | {fraction(s['conditions']['one-shot']['repair_pass'])} | {fraction(s['conditions']['loop']['repair_pass'])} | {fraction(s['strict_rescue'])} |"
        )
    lines += [
        "",
        "## 按错误类型",
        "",
        "| 类型 | 数量 | 单次修复 | Agent |",
        "| --- | ---: | --- | --- |",
    ]
    for group, s in summary["by_category"].items():
        lines.append(
            f"| {group} | {s['repair_cases']} | {fraction(s['conditions']['one-shot']['repair_pass'])} | {fraction(s['conditions']['loop']['repair_pass'])} |"
        )
    lines += [
        "",
        "## 工具与成本",
        "",
        f"正式协议 {fraction(overall['tool_protocol'])}；任务预检 {fraction(overall['task_probe'])}；虚假成功声明 {fraction(overall['false_success_all_tasks'])}；补丁接受 {fraction(overall['patch_acceptance'])}。",
        "",
        "```json",
        json.dumps(overall["patch_failures"], indent=2),
        "```",
        "",
        "| 策略 | 已测修复数 | 平均秒数 | 平均步骤 | 平均模型调用（含预检） |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for condition, s in overall["conditions"].items():
        c = s["cost_repairs"]
        lines.append(
            f"| {condition} | {c['runs']} | {c['mean_seconds']} | {c['mean_steps']} | {c['mean_model_calls']} |"
        )
    lines += [
        "",
        "## 配对结果",
        "",
        "```json",
        json.dumps(overall["paired_repair_outcomes"], indent=2),
        "```",
        "",
        "## 未通过与未知",
        "",
        "| 任务 | 策略 | 状态 | 终止原因 |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        if not real_pass(r):
            lines.append(
                f"| {r['case_id']} | {r['condition']} | {r['status']} | {r['termination_reason']} |"
            )
    selected = {}
    for r in rows:
        if r["condition"] != "loop":
            continue
        d = overall["strict_rescue_details"].get(r["case_id"], {})
        if d.get("rescued"):
            selected.setdefault("strict_rescue", r)
        rejected = any(
            (s.get("tool_call") or {}).get("name") == "apply_patch"
            and s["tool_result"]["status"] != "success"
            for s in r.get("trajectory", [])
        )
        if rejected and real_pass(r):
            selected.setdefault("patch_rejected_then_pass", r)
        if not real_pass(r) and r.get("measurement_status") != "interrupted_unknown":
            selected.setdefault("failure", r)
        if r.get("rejected_finish_count") and real_pass(r):
            selected.setdefault("finish_recovery", r)
    for label, r in selected.items():
        save(OUTPUT / "trajectories" / f"{label}.json", trajectory(r))
    save(OUTPUT / "trajectory_selection.json", {k: r["case_id"] for k, r in selected.items()})
    lines += [
        "",
        "## 配置与工程检查",
        "",
        "```json",
        json.dumps(frozen["model_identity"], indent=2),
        "```",
        "context16384，temperature0，seed42，24步、300秒，最终审核另30秒；执行10秒。实际GPU驻留见每例runtime记录。",
        "",
        "```json",
        json.dumps(
            summary.get("engineering_verification", {"status": "pending"}),
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "## 结论边界",
        "",
        "200只是跨批次任务覆盖数，正确代码样本未计入；旧批次模型运行、来源和未知项分别保留，不能直接合并为生产成功率。",
        "本批不因结果下降、持平或提高而修改Agent或重采样；所有原始轨迹保留。复现需完整冻结输入与相同环境。",
    ]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    save(
        OUTPUT / "artifact_inventory.json",
        {
            p.relative_to(OUTPUT).as_posix(): sha(p.read_bytes())
            for p in sorted(OUTPUT.rglob("*"))
            if p.is_file() and p.name != "artifact_inventory.json"
        },
    )
    print("Reported", len(rows), "attempts; fully observed:", overall["fully_observed"])


if __name__ == "__main__":
    report()
