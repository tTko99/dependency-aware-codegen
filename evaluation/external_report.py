"""Report only checksummed paired artifacts; keep regression and external evidence separate."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from depguard.agent.validation_state import finish_outcome
from evaluation.agent_benchmark import sha
from evaluation.external_validation import OUTPUT, verify_freeze
from evaluation.interview_benchmark import save, verify_manifest
from evaluation.interview_metrics import (
    costs,
    protocol_entered,
    ratio,
    real_pass,
    strict_rescue,
    summarize,
)


def aggregate(cases, rows):
    pairs = {}
    for row in rows:
        key = (row["case_id"], row["condition"])
        if key in pairs:
            raise ValueError("Duplicate attempt; do not select a favorable sample")
        pairs[key] = row
    expected = {(c["id"], condition) for c in cases for condition in ("one-shot", "loop")}
    if set(pairs) - expected:
        raise ValueError("Unexpected case or condition")
    missing = sorted(expected - set(pairs))
    hard = {c["id"] for c in cases if not c["is_control"]}
    controls = {c["id"] for c in cases if c["is_control"]}
    conditions = {}
    for condition in ("one-shot", "loop"):
        subset = [r for r in rows if r["condition"] == condition]
        repairs = [r for r in subset if r["case_id"] in hard]
        control_rows = [r for r in subset if r["case_id"] in controls]
        conditions[condition] = {
            "repair_pass": ratio(sum(real_pass(r) for r in repairs), len(hard)),
            "all_pass": ratio(sum(real_pass(r) for r in subset), len(cases)),
            "controls_preserved": ratio(sum(real_pass(r) and not r.get("candidate_changed")
                and not r.get("patch_count") and r.get("model_calls") == 0 for r in control_rows),
                len(controls)),
            "terminations": dict(Counter(r["termination_reason"] for r in subset)),
            "cost_all": costs(subset), "cost_repairs": costs(repairs),
            "nonpass": [{"case": r["case_id"], "status": r["status"],
                         "reason": r["termination_reason"]} for r in subset if not real_pass(r)]}
    outcome = Counter()
    rescue_details = {}
    for case in sorted(hard):
        a, b = pairs.get((case, "one-shot")), pairs.get((case, "loop"))
        if a is None or b is None:
            outcome["incomplete_pair"] += 1
            continue
        key = ("both_pass" if real_pass(a) and real_pass(b) else
               "agent_only" if real_pass(b) else "one_shot_only" if real_pass(a) else "neither_pass")
        outcome[key] += 1
        rescue_details[case] = strict_rescue(a, b)
    loops = [r for r in rows if r["condition"] == "loop"]
    invoked = [r for r in loops if r.get("agent_invoked", True)]
    claims = [r for r in loops if any((s.get("tool_call") or {}).get("name") == "finish"
              and finish_outcome(s["tool_call"].get("arguments", {})) == "success"
              for s in r.get("trajectory", []))]
    supplementary = summarize(rows)
    return {"planned_cases": len(cases), "repair_cases": len(hard), "control_cases": len(controls),
        "completed_attempts": len(rows), "missing_attempts": missing, "complete": not missing,
        "conditions": conditions, "paired_repair_outcomes": dict(outcome),
        "strict_rescue": ratio(sum(d["rescued"] for d in rescue_details.values()),
                               sum(d["eligible"] for d in rescue_details.values())),
        "strict_rescue_details": rescue_details,
        "task_probe": ratio(sum(r.get("capability_probe", {}).get("status") == "passed"
                                for r in invoked), len(invoked)),
        "tool_protocol": ratio(sum(protocol_entered(r) for r in invoked), len(invoked)),
        "false_success_all_tasks": ratio(sum(not real_pass(r) for r in claims), len(cases)),
        "false_success_claims": ratio(sum(not real_pass(r) for r in claims), len(claims)),
        "rejected_finish_count": sum(r.get("rejected_finish_count", 0) for r in loops),
        "patch_acceptance": supplementary["patch_acceptance"],
        "patch_failures": supplementary["patch_failures"],
        "all_inputs_unchanged": all(r.get("unchanged", False) for r in rows) if rows else None,
        "human_acceptance": "NOT_MEASURED", "production_success_rate": "NOT_MEASURED"}


def fraction(value):
    rate = value["rate"]
    return f"{value['numerator']}/{value['denominator']}" + (
        f" ({rate:.1%})" if rate is not None else "（无有效分母）")


def trajectory(row):
    return {"case_id": row["case_id"], "status": row["status"],
        "termination_reason": row["termination_reason"], "steps": [
            {"step": s["step"], "decision_summary": s.get("decision_summary", ""),
             "tool": (s.get("tool_call") or {}).get("name"),
             "observation": s["tool_result"]["message"][:500],
             "error_code": s["tool_result"].get("evidence", {}).get("error_code"),
             "passed": s["tool_result"].get("evidence", {}).get("passed"),
             "candidate_version": s["candidate_version"], "result": s["tool_result"]["status"]}
            for s in row.get("trajectory", [])]}


def report():
    frozen = verify_freeze()
    all_rows, summaries = [], {}
    for cohort, path in frozen["manifests"].items():
        cases = [c for c in verify_manifest(Path(path))["cases"] if c["cohort"] in {"hard", "control"}]
        index_path = OUTPUT / cohort / "run_manifest.json"
        index = json.loads(index_path.read_text()) if index_path.exists() else {"artifact_hashes": {}}
        rows = []
        for name, expected in index["artifact_hashes"].items():
            artifact = OUTPUT / cohort / name
            if sha(artifact.read_bytes()) != expected:
                raise ValueError("Case artifact changed")
            row = json.loads(artifact.read_text())
            if row["comparison_identity"] != frozen["freeze_id"]:
                raise ValueError("Unpaired model/config identity")
            rows.append(row)
        summaries[cohort] = aggregate(cases, rows)
        all_rows.extend(rows)
    summary = {"freeze_id": frozen["freeze_id"], "model": frozen["model_identity"],
               "cohorts": summaries, "historical_m72": json.loads(
                   Path("results/m72/summary.json").read_text()),
               "historical_metrics_are_not_new_infrastructure_results": True}
    save(OUTPUT / "summary.json", summary)
    (OUTPUT / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in all_rows),
                                        encoding="utf-8")
    external = summaries["external"]
    lines = ["# 独立外部任务评测：真实结果与适用边界", "",
        "本次保持 Agent 实现和提示词不变，先核验公开来源、原始缺陷和参考实现，再冻结任务、实现、配置和指标。",
        "现有 15 例用于回归；新增任务来自 QuixBugs 算法修复基准，不是生产项目缺陷，也不是用户自然提交。",
        "公开基准可能出现在模型训练中。本次没有隐藏测试或人工接受率，不能外推生产修复率。",
        "正确对照使用同源参考版本，与对应修复任务相关，不能作为独立修复样本扩大分母。", "",
        "## 固定条件", "", f"模型身份：`{frozen['model_identity']}`。",
        "本地 Ollama；context=16384；temperature=0；seed=42；每次最多生成2048 tokens；",
        "Agent 最多24步，任务300秒，独立最终审核另30秒；执行/pytest单次10秒。",
        "两组输入、初始诊断、正式测试及验收规则相同；单次修复输出完整代码，Agent 使用补丁与工具。",
        "Agent 可消耗更多调用和总 token，因此不是等计算预算的纯架构因果实验。",
        "配对顺序按案例序号交替；每种条件每例只运行一次，错误、拒绝、超时均保留。", "",
        "## 按来源分别报告", "",
        "| 集合 | 修复任务 | 单次修复通过 | Agent修复通过 | Agent正确对照保持 | 严格多轮救回 |",
        "| --- | ---: | --- | --- | --- | --- |"]
    for name, stats in summaries.items():
        lines.append(f"| {name} | {stats['repair_cases']} | "
            f"{fraction(stats['conditions']['one-shot']['repair_pass'])} | "
            f"{fraction(stats['conditions']['loop']['repair_pass'])} | "
            f"{fraction(stats['conditions']['loop']['controls_preserved'])} | "
            f"{fraction(stats['strict_rescue'])} |")
    lines += ["", "## 外部集配对与成本", "", "```json",
        json.dumps({k: external[k] for k in ["complete", "missing_attempts", "paired_repair_outcomes",
            "task_probe", "tool_protocol", "false_success_all_tasks", "rejected_finish_count",
            "patch_acceptance", "patch_failures"]}, ensure_ascii=False, indent=2), "```", "",
        "| 条件 | 修复任务平均秒数 | 平均模型调用 | 平均步骤 |",
        "| --- | ---: | ---: | ---: |"]
    for condition, stats in external["conditions"].items():
        cost = stats["cost_repairs"]
        lines.append(f"| {condition} | {cost['mean_seconds']} | "
                     f"{cost['mean_model_calls']} | {cost['mean_steps']} |")
    lines += ["", "## 逐例结果", "", "| 集合 | 案例 | 条件 | 状态 | 终止原因 | 秒数 |",
              "| --- | --- | --- | --- | --- | ---: |"]
    for row in all_rows:
        lines.append(f"| {row['evaluation_cohort']} | {row['case_id']} | {row['condition']} | "
                     f"{row['status']} | {row['termination_reason']} | {row['latency']:.2f} |")
    lines += ["", "## 可使用的面试表述", ""]
    if external["complete"]:
        lines += [(f"在未用于本项目控制逻辑调试的 {external['repair_cases']} 个公开算法修复任务上，"
            f"同一30B模型单次修复通过 {fraction(external['conditions']['one-shot']['repair_pass'])}，"
            f"Agent通过 {fraction(external['conditions']['loop']['repair_pass'])}；"
            "固定输入、测试和配置，保留全部失败轨迹。结果仅适用于该公开单文件基准。")]
    else:
        lines += ["评测尚未完成，不能使用最终通过率。"]
    lines += ["", "不应声称：真实用户接受率、工业仓库修复率、无训练污染或普遍优于单次修复。",
        "若 Agent 不优于单次修复，按原结果报告；本轮不针对这些案例调参。", "",
        "来源、筛选与上游许可见 `data/external_eval_v1/upstream` 和 `screening.json`；",
        "参考解预检见 `preflight`；冻结凭据见 `freeze.json`；每例原始记录见 external/regression。",
        "本轮任务均为 dry-run；完整轨迹记录公开决策摘要，不记录隐藏推理。"]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    loops = [r for r in all_rows if r["condition"] == "loop" and not r.get("is_control")]
    representatives = {}
    for row in loops:
        key = "rejected_patch" if any((s.get("tool_call") or {}).get("name") == "apply_patch"
            and s["tool_result"]["status"] != "success" for s in row.get("trajectory", [])) else None
        if key:
            representatives.setdefault(key, row)
        if not real_pass(row):
            representatives.setdefault("final_failure", row)
        detail = summaries[row["evaluation_cohort"]]["strict_rescue_details"].get(row["case_id"], {})
        if detail.get("rescued"):
            representatives.setdefault("strict_rescue", row)
        if row.get("rejected_finish_count"):
            representatives.setdefault("finish_recovery", row)
        representatives.setdefault("first_repair", row)
    for label, row in representatives.items():
        save(OUTPUT / "trajectories" / (label + ".json"), trajectory(row))
    save(OUTPUT / "trajectory_selection.json", {"observed": {k: r["case_id"]
        for k, r in representatives.items()}, "not_observed": [k for k in (
            "strict_rescue", "rejected_patch", "final_failure", "finish_recovery")
            if k not in representatives]})
    save(OUTPUT / "artifact_inventory.json", {p.relative_to(OUTPUT).as_posix(): sha(p.read_bytes())
        for p in sorted(OUTPUT.rglob("*")) if p.is_file() and p.name != "artifact_inventory.json"})
    print(json.dumps({k: {"complete": s["complete"], "conditions": {
        c: v["repair_pass"] for c, v in s["conditions"].items()}} for k, s in summaries.items()}))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    report()
