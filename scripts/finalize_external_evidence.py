"""Correct derived reporting for audited interruption; never change case evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.external_report import fraction, trajectory
from evaluation.external_validation import OUTPUT, verify_freeze
from evaluation.interview_benchmark import save
from evaluation.interview_metrics import costs, ratio, real_pass


def observed(row):
    return row.get("measurement_status") != "interrupted_unknown"


def adjust(summary, rows):
    result = copy.deepcopy(summary)
    for cohort, stats in result["cohorts"].items():
        subset = [r for r in rows if r["evaluation_cohort"] == cohort]
        unknown = [r for r in subset if not observed(r)]
        stats["fully_observed"] = stats["complete"] and not unknown
        stats["interrupted_attempts"] = [r["case_id"] + ":" + r["condition"] for r in unknown]
        stats["observed_attempts"] = sum(observed(r) for r in subset)
        stats["recorded_attempts"] = len(subset)
        stats["completed_attempts"] = stats["observed_attempts"]
        stats["complete_means"] = "All planned attempts have completed or audited records; see fully_observed"
        for condition, metrics in stats["conditions"].items():
            selected = [r for r in subset if r["condition"] == condition]
            measured = [r for r in selected if observed(r)]
            repairs = [r for r in measured if not r["is_control"]]
            metrics["cost_all"] = costs(measured)
            metrics["cost_repairs"] = costs(repairs)
            metrics["unknown_cost_attempts"] = len(selected) - len(measured)
            metrics["observed_repair_pass"] = ratio(sum(real_pass(r) for r in repairs), len(repairs))
            metrics["observed_nonpass"] = [r for r in metrics["nonpass"]
                if r["reason"] != "evaluation_interrupted_unknown_result"]
        pairs = {}
        for row in subset:
            if not row["is_control"]:
                pairs.setdefault(row["case_id"], {})[row["condition"]] = row
        counts = {}
        for pair in pairs.values():
            if len(pair) != 2:
                key = "incomplete_pair"
            elif not all(observed(r) for r in pair.values()):
                key = "interrupted_pair"
            else:
                a, b = real_pass(pair["one-shot"]), real_pass(pair["loop"])
                key = "both_pass" if a and b else "agent_only" if b else "one_shot_only" if a else "neither_pass"
            counts[key] = counts.get(key, 0) + 1
        stats["paired_repair_outcomes"] = counts
    result["interruption_reporting"] = {
        "policy": "Unknown outcome is not a demonstrated PASS and is not a model failure; "
                  "retain planned denominator, exclude unmeasured costs and protocol, never retry.",
        "raw_derived_report": "recovery/frozen_report_summary.json",
        "finalizer_sha256": sha(Path(__file__).read_bytes())}
    return result


def main():
    verify_freeze()
    summary_path = OUTPUT / "summary.json"
    report_path = OUTPUT / "report.md"
    archive = OUTPUT / "recovery"
    for source, name in ((summary_path, "frozen_report_summary.json"),
                         (report_path, "frozen_report.md")):
        destination = archive / name
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
    original = json.loads((archive / "frozen_report_summary.json").read_text())
    rows = [json.loads(line) for line in (OUTPUT / "cases.jsonl").read_text().splitlines()]
    summary = adjust(original, rows)
    verification = OUTPUT / "verification.json"
    if verification.exists():
        summary["engineering_verification"] = json.loads(verification.read_text())
    save(summary_path, summary)
    followups = []
    recovered_rejections = []
    for row in rows:
        if row["condition"] != "loop" or not real_pass(row):
            continue
        detail = summary["cohorts"][row["evaluation_cohort"]]["strict_rescue_details"].get(row["case_id"], {})
        if detail.get("first_repair_status") == "FAIL":
            item = {"case_id": row["case_id"], "cohort": row["evaluation_cohort"],
                    "strict_rescue": detail["rescued"], "failure_step": detail["failure_observation_step"]}
            followups.append(item)
            save(OUTPUT / "trajectories" / ("later_repair_" + row["case_id"] + ".json"), trajectory(row))
        rejected = [s["step"] for s in row.get("trajectory", [])
            if (s.get("tool_call") or {}).get("name") == "apply_patch"
            and s["tool_result"]["status"] != "success"]
        if rejected:
            recovered_rejections.append(row["case_id"])
            if len(recovered_rejections) == 1:
                save(OUTPUT / "trajectories/patch_rejection_recovered.json", trajectory(row))
    save(OUTPUT / "later_repair_examples.json", followups)
    save(OUTPUT / "patch_rejection_recoveries.json", recovered_rejections)
    lines = ["# 冻结外部评估：最终结果与限制", "",
        "保持 Agent、提示词、任务和指标不变，比较同一 Qwen3-Coder 30B 的单次修复与 Agent。",
        "新增 29 个 QuixBugs 公开算法缺陷和 10 个同源正确对照；原 15 例单列为开发期间使用过的回归集。",
        "筛选在模型运行前完成：9 个图结构任务超出单文件适配范围，2 个被既有静态风险规则拒绝。",
        "未为凑齐 40 例放宽规则，也未根据模型表现更换任务。", "",
        "## 结果", "",
        "| 集合 | 单次修复：缺陷任务 | Agent：缺陷任务 | Agent：正确对照 | 严格多轮救回 |",
        "| --- | --- | --- | --- | --- |"]
    for cohort, stats in summary["cohorts"].items():
        a, b = stats["conditions"]["one-shot"], stats["conditions"]["loop"]
        lines.append(f"| {cohort} | {fraction(a['repair_pass'])} | {fraction(b['repair_pass'])} | "
                     f"{fraction(b['controls_preserved'])} | {fraction(stats['strict_rescue'])} |")
    external = summary["cohorts"]["external"]
    a = external["conditions"]["one-shot"]["repair_pass"]["numerator"]
    b = external["conditions"]["loop"]["repair_pass"]["numerator"]
    if b < a:
        lines += ["", (f"本轮外部集 Agent 已证明通过数低于单次修复（{b} 对 {a}）。"
            "这组结果不支持 Agent 提高修复成功率；停止针对本评估集优化，保留为项目限制。")]
    lines += ["", "### 一次外部中断", "",
        "`qb_levenshtein` 的 Agent 运行留下启动标记，但进程退出后没有最终记录；未重新运行。",
        "它保留在计划分母内，标记为结果未知，不计为已证明通过，也不归因于模型失败。",
        "该记录中的零耗时、零调用只是占位值；本报告已将其排除出成本均值和协议分母。",
        "原始派生报表保存在 `recovery/frozen_report*`；修正只作用于统计，未改变案例证据。", "",
        "## 成本与协议（只统计实际观测）", "",
        "| 集合/条件 | 测得修复数 | 平均秒数 | 平均模型调用 | 平均步骤 |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for cohort, stats in summary["cohorts"].items():
        for condition, metrics in stats["conditions"].items():
            c = metrics["cost_repairs"]
            lines.append(f"| {cohort}/{condition} | {c['runs']} | {c['mean_seconds']:.2f} | "
                         f"{c['mean_model_calls']:.2f} | {c['mean_steps']:.2f} |")
    for cohort, stats in summary["cohorts"].items():
        lines += ["", (f"{cohort}：任务预检 {fraction(stats['task_probe'])}；"
                  f"正式协议 {fraction(stats['tool_protocol'])}；"
                  f"虚假成功 {fraction(stats['false_success_all_tasks'])}；"
                  f"patch 接受 {fraction(stats['patch_acceptance'])}。"), ""]
    lines += ["任务调用数包括各自的独立协议预检；表内耗时包含宿主验证与最终审核。",
        "全局独立预检的冷加载时间另见capability_probe.json；未知中断的成本不填补。", "",
        "外部集补丁拒绝分布：", "```json",
        json.dumps(external["patch_failures"], ensure_ascii=False, indent=2), "```", ""]
    lines += ["## 所有未通过及未知结果", "",
        "| 集合 | 案例 | 条件 | 状态 | 原因 |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        if not real_pass(row):
            lines.append(f"| {row['evaluation_cohort']} | {row['case_id']} | {row['condition']} | "
                         f"{row['status']} | {row['termination_reason']} |")
    lines += ["", "## 工程检查", "", "```json",
        json.dumps(summary.get("engineering_verification", {"status": "not recorded"}),
                   ensure_ascii=False, indent=2), "```", "",
        "工程测试验证控制逻辑，不计入模型修复成功数。", "",
        "## 真实后续修复", "",
        "以下案例在首次有效patch后检查失败，随后修复并最终通过；只有满足单次修复也失败等完整条件时，才计入严格救回。",
        "```json", json.dumps(followups, ensure_ascii=False, indent=2), "```", "",
        f"补丁被拒绝但最终通过的案例：{', '.join(recovered_rejections) or '未观察到'}。",
        "`trajectories/rejected_patch.json` 展示补丁被拒绝；`finish_recovery.json` 展示提前finish后补齐检查。",
        "轨迹只包含公开动作摘要、工具结果及版本，不包含隐藏推理。", "",
        "## 配置与可复核证据", "", "```json",
        json.dumps(summary["model"], ensure_ascii=False, indent=2), "```", "",
        ("context=16384，temperature=0，seed=42，每次输出最多2048 tokens；Agent最多24步、300秒，"
        "最终独立审核另30秒；执行/pytest单次10秒。模型驻留检查为100% GPU。"),
        "配对顺序交替，每例每条件一次；两组相同输入、初始诊断、正式测试和验收政策。",
        "Agent 使用更多调用和总 token，不能把差异解释为等计算预算下的架构因果效应。",
        "历史 M7.2 的 Ollama 版本不同，本轮两组均重新运行；没有择优复用历史结果。", "",
        "逐例完整记录：`cases.jsonl` 与 `external/`、`regression/`；统计：`summary.json`；",
        "冻结及哈希：`freeze.json`；独立预检：`capability_probe.json`；代表轨迹：`trajectories/`；",
        "来源许可、筛选及原始/参考代码预检：`data/external_eval_v1/`；方法：`docs/EXTERNAL_EVALUATION.md`。", "",
        "## 结论边界", "",
        "这是一组未用于本项目 Agent 控制逻辑调试的公开单文件算法任务，不是生产缺陷或真实用户样本。",
        "公开基准可能进入模型预训练；正式测试对模型可见，没有独立隐藏测试，也未测量人工接受率。",
        "10 个正确对照与修复案例同源，不能当作独立缺陷样本扩大修复分母。",
        "只可报告在这组冻结任务上的结果，不可据此声称通用修复成功率或普遍优于单次修复。",
        "本轮不再依据评估失败调整 Agent 或提示词。所有失败、拒绝、超时和中断均保留。",
        "真实使用时仍需提供可执行需求测试并人工审查候选；未来用户样本应独立登记、一次运行、单独报告。"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    verify_freeze()
    save(OUTPUT / "artifact_inventory.json", {p.relative_to(OUTPUT).as_posix(): sha(p.read_bytes())
        for p in sorted(OUTPUT.rglob("*")) if p.is_file() and p.name != "artifact_inventory.json"})
    print("Derived reports finalized; case artifacts and frozen implementation unchanged")


if __name__ == "__main__":
    main()
