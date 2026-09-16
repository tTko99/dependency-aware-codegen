"""Before/after report; unchanged strict-rescue and final-pass metric functions."""
import argparse
import json
from pathlib import Path

from evaluation.interview_benchmark import save
from evaluation.interview_metrics import (
    protocol_entered,
    ratio,
    strict_rescue,
    summarize,
    validation_counts,
)
from evaluation.interview_report import inventory, load_rows
from evaluation.m72_validation import BEFORE, protected_hashes


def fraction(value):
    return f"{value['numerator']}/{value['denominator']}" + (
        f" ({value['rate']:.1%})" if value["rate"] is not None else " (N/A)")


def report(root):
    assert json.loads((root / "protected_before.json").read_text()) == protected_hashes()
    rows, old = load_rows(root / "comparison"), load_rows(BEFORE / "existing")
    assert len(rows) == len(old) == 30
    baseline = [r for r in rows if r["condition"] == "one-shot"]
    assert baseline == [r for r in old if r["condition"] == "one-shot"], "Baseline must not change"
    infra = load_rows(root / "infrastructure") if (root / "infrastructure/run_manifest.json").exists() else []
    current, previous = summarize(rows + infra), summarize(old)
    loops = [r for r in rows if r["condition"] == "loop"]
    triggered = [r for r in loops if r.get("agent_invoked", True)]
    # Controls skipped by the deterministic gate have no protocol attempt.
    # Select the requested population without changing rescue or real_pass rules.
    protocol = ratio(sum(protocol_entered(r) for r in triggered), len(triggered))
    probes = ratio(sum(r["capability_probe"]["status"] == "passed" for r in triggered), len(triggered))
    current["tool_protocol"] = protocol
    current["capability_probe"] = probes
    false_tasks = ratio(current["false_success"]["numerator"], len(loops))
    pairs = {(r["case_id"], r["condition"]): r for r in rows}
    details = {r["case_id"]: strict_rescue(pairs[r["case_id"], "one-shot"], r) for r in loops}
    finish_events = []
    for row in loops:
        rejected = [s for s in row["trajectory"] if s["tool_result"].get("evidence", {}).get(
            "error_code") == "FINISH_PRECONDITION_FAILED"]
        if rejected:
            finish_events.append({"case_id": row["case_id"], "rejected_steps": [s["step"] for s in rejected],
                "later_actions": [{"step": s["step"], "tool": (s.get("tool_call") or {}).get("name")}
                    for s in row["trajectory"] if s["step"] > rejected[0]["step"]],
                "final_status": row["status"]})
    result = {"milestone": "M7.2", "m71": previous, "m72": current,
        "triggered_repair_cases": len(triggered), "formal_protocol": protocol,
        "triggered_capability_probes": probes, "false_success_all_tasks": false_tasks,
        "finish_precondition_events": finish_events, "case_rescue_evidence": details,
        "protected_inputs_configs_manifests_and_m71_unchanged": True,
        "one_shot_baseline": "all 15 M7.1 artifacts reused byte-for-byte; no new one-shot inference",
        "standalone_probe": json.loads((root / "capability_probe.json").read_text()),
        "resolved_config": json.loads((root / "resolved_config.json").read_text()),
        "runtime": json.loads((root / "runtime_after.json").read_text())}
    if (root / "checks.json").exists():
        result["checks"] = json.loads((root / "checks.json").read_text())
    save(root / "summary.json", result)
    (root / "cases.jsonl").write_text("".join(json.dumps({**r,
        "validation_counts": validation_counts(r), "strict_rescue": details[r["case_id"]]}) + "\n"
        for r in rows), encoding="utf-8")
    def metric(summary, name):
        return summary["conditions"]["loop"][name]
    lines = ["# M7.2：最后一次通用 Agent 行为修正与冻结复测", "",
        "## Before / after", "",
        "| 指标 | M7.1 | M7.2 |", "| --- | --- | --- |",
        f"| Agent 最终通过 | {fraction(metric(previous, 'true_pass'))} | {fraction(metric(current, 'true_pass'))} |",
        f"| 严格多轮救回 | {fraction(previous['strict_rescue'])} | {fraction(current['strict_rescue'])} |",
        f"| control 保持 | {fraction(metric(previous, 'controls'))} | {fraction(metric(current, 'controls'))} |",
        f"| 虚假成功 / 全部任务 | {fraction(ratio(previous['false_success']['numerator'], 15))} | {fraction(false_tasks)} |"]
    for key, title in (("mean_steps", "平均步骤"), ("mean_model_calls", "平均模型调用数"), ("mean_seconds", "平均耗时（秒）")):
        lines.append(f"| {title} | {metric(previous, 'cost')[key]:.3f} | {metric(current, 'cost')[key]:.3f} |")
    lines += ["", f"正式协议（仅触发修复的案例）：{fraction(protocol)}；触发修复 {len(triggered)}/15。",
        f"正式任务独立 probe：{fraction(probes)}；运行前完整隔离 probe：{result['standalone_probe']['result']['status']}。",
        f"原始指标函数的虚假成功率（成功声明任务为分母）：{fraction(current['false_success'])}。",
        ("全部任务分母 15 的虚假成功行按用户要求另列；分子、最终真实 PASS、strict_rescue 函数均未修改。"
        "被拒绝但后来验证成功的 finish 不构成最终虚假成功；所有拒绝事件另存。"), "",
        "## 冻结与公平性", "",
        ("复用 `results/qwen3_validation/frozen/manifest.json` 和 `configs/m7_qwen3_30b.json`，均未改写。"
        "模型 digest、Ollama 版本、温度 0、context 16384、24 步、300 秒及正式测试/验证规则保持一致。"
        "M7.1 所有 artifact 和评估源/测试/reference/config/manifest 的哈希均与运行前一致。"),
        ("one-shot 原 15 份 artifact 逐字节复用，没有重新推理或选择较好结果。两组 prompt 本来不同；"
        "本次仅修改通用控制逻辑/说明与状态 observation，没有案例专用提示。"),
        ("初检采用同一真实验证工具；正确原始 candidate 直接 NO_REPAIR_NEEDED、agent_invoked=false，"
        "不调用模型也不应用 patch。低层 AgentLoop.run 用于已有状态的继续运行；CLI 和 M7.2 使用 run_agent 门禁。"),
        ("M7.2 的 300 秒上限包含门禁、probe 和 loop；M7.1 初检在 loop 上限之外。"
        "修复任务最终独立审核均另限 30 秒；执行工具均 10 秒。未触发修复的 control 复用初检证据。平均成本包含全部 15 例，control 为零模型调用。"), "",
        "## 逐例结果", "",
        "| 案例 | M7.1 | M7.2 | Agent invoked | 步数 | 接受 patch | finish 拒绝 | 终止 | 严格救回 |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |"]
    old_loops = {r["case_id"]: r for r in old if r["condition"] == "loop"}
    for r in loops:
        lines.append(f"| {r['case_id']} | {old_loops[r['case_id']]['status']} | {r['status']} | "
            f"{r.get('agent_invoked')} | {len(r['trajectory'])} | {r['patch_count']} | "
            f"{r.get('rejected_finish_count', 0)} | {r['termination_reason']} | {details[r['case_id']]['rescued']} |")
    lines += ["", "## 提前 finish 的实际表现", "",
        f"本轮有 {len(finish_events)} 个案例收到 FINISH_PRECONDITION_FAILED。", "",
        "```json", json.dumps(finish_events, ensure_ascii=False, indent=2), "```", "",
        "## 真实代表轨迹", ""]
    selected = []
    for r in loops:
        if (r.get("rejected_finish_count") or details[r["case_id"]]["first_repair_status"] == "FAIL"
                or any((s.get("tool_call") or {}).get("name") == "apply_patch"
                       and s["tool_result"]["status"] != "success" for s in r["trajectory"])):
            selected.append(r)
    for r in loops:
        if len(selected) >= 3:
            break
        if r not in selected:
            selected.append(r)
    for r in selected:
        name = f"trajectories/{r['case_id']}.json"
        trace = [{"step": s["step"], "decision_summary": s["decision_summary"],
            "tool": (s.get("tool_call") or {}).get("name"), "candidate_version": s["candidate_version"],
            "observation_summary": {k: s["tool_result"].get("evidence", {}).get(k) for k in (
                "passed", "error_code", "missing_checks", "failed_checks", "stale_checks", "validation_state")},
            "result": s["tool_result"]["status"]} for s in r["trajectory"]]
        save(root / name, {"case_id": r["case_id"], "final_status": r["status"], "trajectory": trace})
        lines.append(f"- [{r['case_id']}]({name})：{r['status']}；strict rescue={details[r['case_id']]['rescued']}。")
    lines += ["", "## 完整指标", "", "```json", json.dumps({
        "patch_acceptance": current["patch_acceptance"], "patch_failures": current["patch_failures"],
        "cost": metric(current, "cost"), "infrastructure_only": current["infrastructure_only"],
        "checks": result.get("checks", {})}, indent=2, ensure_ascii=False), "```", "",
        "## 限制与停止条件", "",
        ("这是最后一次通用行为修正；只运行一次正式冻结复测，没有筛掉失败、增加案例或选择性重跑。"
        "工具协议、代码通过率与严格多轮收益分别报告。小型可见测试、手工单文件集不能证明泛化；"
        "进程、临时目录和 timeout 不是安全沙箱。ScriptedTestModel 只用于基础设施测试。"),
        f"本轮 Agent 通过 {fraction(metric(current, 'true_pass'))}；复用 one-shot {fraction(current['conditions']['one-shot']['true_pass'])}。",
        "无论本轮优于、持平还是低于 one-shot，都不再针对该评估集继续优化。没有真实严格救回时如实保留 0。",
        ("修改及复现说明见 docs/M7_2.md；checks.json、comparison/run_manifest.json、cases.jsonl、"
        "summary.json、protected_before.json 提供复核来源。未执行 Git 操作，未调用云模型。"), ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    inventory(root)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="results/m72")
    report(Path(parser.parse_args().output_dir))
