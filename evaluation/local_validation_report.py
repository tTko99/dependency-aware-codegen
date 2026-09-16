"""Rebuild the local 30B report from immutable, checksummed paired artifacts."""
import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.interview_benchmark import save, verify_manifest
from evaluation.interview_metrics import strict_rescue, summarize, validation_counts
from evaluation.interview_report import inventory, load_rows


def fraction(value):
    rate = f"{100 * value['rate']:.1f}%" if value["rate"] is not None else "N/A"
    return f"{value['numerator']}/{value['denominator']} ({rate})"


def audit_smoke(row):
    steps = row["trajectory"]
    patches = [s for s in steps if (s.get("tool_call") or {}).get("name") == "apply_patch"
               and s["tool_result"]["status"] == "success"]
    return {
        "native_calls_only": all(s.get("raw_response", {}).get("tool_calls") for s in steps),
        "ids_preserved": all(s["tool_call"].get("call_id") for s in steps),
        "candidate_revision_increased": bool(patches) and all(
            int(s["state_transition"]["to_version"].split(":")[0]) >
            int(s["state_transition"]["from_version"].split(":")[0]) for s in patches),
        "patch_invalidates_checks": bool(patches) and all(
            not s["state_transition"]["checks_after"] for s in patches),
        "current_pytest_pass": any((s.get("tool_call") or {}).get("name") == "run_pytest"
            and s["tool_result"]["evidence"].get("passed") is True
            and s["candidate_version"] == row["candidate_version"] for s in steps),
        "finish_and_host_pass": row["termination_reason"] == "finish" and row["status"] == "PASS"
            and row["final_verification"]["host_status"] == "PASS",
        "source_and_tests_unchanged": row["unchanged"],
    }


def report(root):
    manifest = verify_manifest(root / "frozen/manifest.json")
    rows = load_rows(root / "existing")
    expected = {c["id"] for c in manifest["cases"] if c["cohort"] in {"hard", "control"}}
    assert {(r["case_id"], r["condition"]) for r in rows} == {
        (case, arm) for case in expected for arm in ("one-shot", "loop")}, "Incomplete paired run"
    infra = load_rows(root / "infrastructure")
    summary = summarize(rows + infra)
    run = json.loads((root / "existing/run_manifest.json").read_text())
    probe = json.loads((root / "probe_fair.json").read_text())
    smoke = json.loads((root / "smoke_fair.json").read_text())
    summary["standalone_probe"] = probe["result"]
    summary["smoke_audit"] = audit_smoke(smoke["result"])
    assert all(summary["smoke_audit"].values()), "Smoke invariant failed"
    summary["termination_counts"] = dict(Counter(r["termination_reason"] for r in rows if r["condition"] == "loop"))
    summary["model_identity"] = {key: run[key] for key in ("model", "model_digest", "ollama_version")}
    summary["resolved_config"] = run["resolved_config"]
    for name in ("checks", "runtime_final"):
        path = root / f"{name}.json"
        if path.exists():
            summary[name] = json.loads(path.read_text())
    replay = root / "sanity_replay/summary.json"
    if replay.exists():
        summary["engineering_sanity_replay"] = json.loads(replay.read_text())
    pairs = {(r["case_id"], r["condition"]): r for r in rows}
    details = {case: strict_rescue(pairs[case, "one-shot"], pairs[case, "loop"]) for case in sorted(expected)}
    summary["case_rescue_evidence"] = details
    save(root / "summary.json", summary)
    save(root / "resolved_config.json", run["resolved_config"])
    (root / "cases.jsonl").write_text("".join(json.dumps({**r,
        "validation_counts": validation_counts(r), "strict_rescue": details[r["case_id"]]}) + "\n"
        for r in rows), encoding="utf-8")
    loops = [r for r in rows if r["condition"] == "loop"]
    categories = {
        "strict_rescue": [r for r in loops if details[r["case_id"]]["rescued"]],
        "within_loop_recovery_not_strict": [r for r in loops if r["status"] == "PASS"
            and details[r["case_id"]]["first_repair_status"] == "FAIL"
            and not details[r["case_id"]]["rescued"]],
        "patch_rejection_retry": [r for r in loops if any(
            (s.get("tool_call") or {}).get("name") == "apply_patch" and
            s["tool_result"]["status"] != "success" for s in r["trajectory"])],
        "failure_or_stop": [r for r in loops if r["status"] != "PASS"],
        "baseline_failure_comparison": [r for r in loops if pairs[r["case_id"], "one-shot"]["status"] == "FAIL"],
        "control": [r for r in loops if r["is_control"]],
        "ordinary_pass": [r for r in loops if r["status"] == "PASS" and not r["is_control"]],
    }
    traces, selected = [], set()
    for category, candidates in categories.items():
        row = next((r for r in candidates if r["case_id"] not in selected), None)
        if row is None:
            continue
        selected.add(row["case_id"])
        name = f"trajectories/{category}_{row['case_id']}.json"
        trace = []
        for s in row["trajectory"]:
            result = s["tool_result"]
            evidence = result.get("evidence", {})
            trace.append({"step": s["step"], "decision_summary": s["decision_summary"],
                "tool": (s.get("tool_call") or {}).get("name"),
                "observation_summary": {"message": result["message"], "passed": evidence.get("passed"),
                    "error_code": evidence.get("error_code"), "missing_checks": evidence.get("missing_checks")},
                "candidate_version": s["candidate_version"], "result": result["status"]})
        save(root / name, {"case_id": row["case_id"], "category": category, "mode": "live",
                           "final_status": row["status"], "trajectory": trace})
        traces.append((category, row["case_id"], name))
    lines = ["# Qwen3-Coder 30B：真实本地 Agent 验证报告", "",
        "## 结论", "",
        f"完整 capability probe：{probe['result']['status']}；正式 probe 成功率：{fraction(summary['capability_probe'])}。",
        f"正式工具协议：{fraction(summary['tool_protocol'])}；严格多轮救回：{fraction(summary['strict_rescue'])}。",
        "本报告只将 Ollama 实际推理计入模型指标，ScriptedTestModel 仅用于安全和生命周期回归。", "",
        "| 指标 | 结果 |", "| --- | --- |"]
    for arm, values in summary["conditions"].items():
        for key in ("true_pass", "hard_pass", "controls"):
            lines.append(f"| {arm} {key} | {fraction(values[key])} |")
    for key in ("patch_acceptance", "false_success"):
        lines.append(f"| {key} | {fraction(summary[key])} |")
    for key, value in summary["infrastructure_only"].items():
        lines.append(f"| 基础设施 {key} | {fraction(value)} |")
    lines += ["", "## 同模型逐例对照", "",
        "| 案例 | one-shot | Agent 首次修复 | Agent 最终 | 步数 | 接受 patch | 终止 | 严格救回 |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |"]
    for case in sorted(expected):
        a, b = pairs[case, "one-shot"], pairs[case, "loop"]
        d = details[case]
        lines.append(f"| {case} | {a['status']} | {d['first_repair_status']} | {b['status']} | "
                     f"{len(b['trajectory'])} | {b['patch_count']} | {b['termination_reason']} | {d['rescued']} |")
    lines += ["", "## 口径与实验配置", "",
        f"模型 `{run['model']}`；digest `{run['model_digest']}`；Ollama `{run['ollama_version']}`。",
        ("两组使用同一冻结输入、requirement、可见正式测试、初始宿主检查投影、生成参数与宿主最终验证。"
        "one-shot 只生成一次完整代码；正确 control 在宿主初检通过后不调用修复模型。"
        "Agent 可自行选择工具和多次内存 patch，必须 finish，最终独立重验。"),
        ("context 16384，temperature 0，seed 42，top_p 1，repeat_penalty 1；每次生成上限 2048 token，"
        "stream false，keep_alive 10m。未降低 context。运行时驻留证据见 probe_fair.json 和 runtime_final.json。"),
        ("Agent 最多 24 步，loop 全局期限 300 秒（含 probe 和工具），probe 最多 90 秒；"
        "one-shot 初检和生成期限 300 秒；两组最终宿主重验另限 30 秒。执行工具每次 10 秒。"
        "Agent 的初检在 loop 期限之前；每组初检耗时计入总 latency。此为相同每次调用配置，非相同总 token/时间预算。"),
        ("初始证据仅作上下文；候选变更清空旧检查。最近 6 步保留完整调用，较早步骤摘要化；"
        "单个 observation 上限 6000 字符，完整工具结果保存在逐例 JSON。"),
        ("严格救回必须同时满足 one-shot 失败、Agent 首次接受 patch 后正式验证失败、"
        "模型读取失败 observation 后应用不同 patch、原生 finish、宿主真实 PASS。"
        "首次 patch 直接通过、patch 解析失败后重发，均不能单独构成严格救回。"),
        "本轮 one-shot 存在实际失败，故不触发 N=0 时新增困难集合的条件；没有重复采样筛选失败。", "",
        "## 关键真实观察", "",
        "- `weights`：one-shot 漏掉负数输入拒绝；Agent 第一次 patch 已通过。因此计入分母 N=1，但不计严格救回。",
        ("- `chunks`：第 2 步首次 patch 后，第 3 步 pytest 仍失败；第 4 步补上非正 size 检查，"
        "第 5 步 pytest 通过，第 9 步 finish，宿主 PASS。这是真实 observation 驱动的二次修复；"
        "但同模型 one-shot 已通过，因此不满足严格对照救回定义。"),
        ("- `json_names`、`median`、`runs`：修复后 pytest 通过，但缺少当前版本 execute/API/package 证据就 finish。"
        "宿主当场 FAIL；后续独立审核通过也不覆盖正式失败，虚假成功 3/15。"),
        "- `control_stable_unique`：原代码与初检正确，Agent 仍做了冗余 patch。最终验证通过但 control 保持不通过，故为 4/5。",
        "", "## 真实轨迹", ""]
    for category, case, name in traces:
        lines.append(f"- [{category}: {case}]({name})")
    for category in ("strict_rescue", "patch_rejection_retry", "failure_or_stop"):
        if not categories[category]:
            lines.append(f"- `{category}`：本轮没有实际发生，不补造此类轨迹。")
    lines += ["", "## 成本和拒绝分布", "", "```json", json.dumps({
        "cost": {k: v["cost"] for k, v in summary["conditions"].items()},
        "patch_failures": summary["patch_failures"], "termination_counts": summary["termination_counts"],
    }, indent=2, ensure_ascii=False), "```", "",
        ("patch_acceptance 的分母就是 patch 调用总数；拒绝按原始 error_code 分类。"
        "未发生的解析/context/路径/语法拒绝为 0。模型调用与 token 包含隔离 probe；正式 steps 不含 probe。"), "",
        "## 根因与实现改动", "",
        ("30B 在旧适配器上已通过一次完整 probe（probe_before.json），因此不能证明旧 7B 的 0/15 都是实现错误。"
        "本轮补齐 native arguments 为 object 或 JSON 字符串的兼容、保留 call ID/function index 和 tool 关联，"
        "以及 probe 的 response model、参数类型、终止与 finish 参数审计。没有解析 content 中的伪工具 JSON。"),
        ("公平性修正：新配置明确启用 shared_initial_evidence，两组获得相同宿主诊断格式。"
        "旧冻结配置不变。严格救回统计新增显式 finish 证据要求。"), "",
        "## 历史与当前证据的区别", "",
        "- qwen2.5-coder:7b 历史 one-shot：困难 8/10，control 5/5；旧 Agent 原生协议 0/15。",
        "- 用户独立 PowerShell 最小 tool-call 验证：外部前置证据，未加入此报告模型运行分母。",
        "- qwen3-coder:30b 完整隔离 probe 和 smoke：本次保存的实测 artifact；正式比较另计 15 对。",
        "- ScriptedTestModel：只用于本轮 infrastructure 目录的拒绝、原子 patch、rollback 回归。",
        "- engineering sanity 历史真实推理结果为修复 8/8、control 2/2；本轮 replay 如有，明确标记历史输出回放。", "",
        "## 安全、限制与复核", "",
        f"所有正式 source/test SHA-256 保持不变：{summary['all_live_inputs_unchanged']}；原冻结 manifest 已重新校验。",
        ("默认 dry-run，只更新内存候选；目标文件未写入。执行前有权限、输入哈希、AST 风险检查；"
        "subprocess、临时目录和 timeout 是进程/超时边界，不是安全沙箱。"),
        ("这是小型、可见测试、单文件手工缺陷集，单次采样；不能外推仓库级修复能力，"
        "也不能将 7B 与 30B 的差异归因于 loop。纯本地运行，无云模型或 API Key。"),
        ("运行入口见 docs/QWEN3_LOCAL_VALIDATION.md。summary.json、cases.jsonl 与各条件逐例 JSON "
        "均由同一校验过的 run manifest 派生。测试与 lint 结果见 checks.json；"
        "原始模型日志仅保留公开内容/工具调用/usage，不记录 thinking 字段或环境秘密。"), ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    inventory(root)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results/qwen3_validation")
    report(Path(parser.parse_args().root))
