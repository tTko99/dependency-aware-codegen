"""All report numbers derive from the same summary object and checksummed case artifacts."""
import json

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import save
from evaluation.interview_metrics import strict_rescue, summarize, validation_counts


def load_rows(root):
    index = json.loads((root / "run_manifest.json").read_text())
    rows = []
    for name, expected in index["artifact_hashes"].items():
        path = root / name
        if sha(path.read_bytes()) != expected:
            raise ValueError("Case artifact hash changed")
        rows.append(json.loads(path.read_text()))
    return rows


def fraction(value):
    return f"{value['numerator']}/{value['denominator']}" + (" (N/A)" if not value["denominator"] else "")


def inventory(root):
    save(root / "artifact_inventory.json", {"files": [
        {"path": p.as_posix(), "sha256": sha(p.read_bytes())} for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "artifact_inventory.json"]})


def report(root, infrastructure=None, sanity=None):
    rows = load_rows(root)
    infra = load_rows(infrastructure) if infrastructure else []
    summary = summarize(rows + infra)
    if sanity:
        summary["engineering_sanity"] = json.loads((sanity / "summary.json").read_text())
    save(root / "summary.json", summary)
    (root / "cases.jsonl").write_text("".join(json.dumps({**r, "validation_counts": validation_counts(r)})+"\n" for r in rows), encoding="utf-8")
    pairs = {(r["case_id"], r["condition"]): r for r in rows}
    lines = ["# M7：受控单文件修复评估", "",
        "第一版系统使用确定性依赖/API 验证和一次模型修复。升级版将修复过程改为 observation 驱动的工具调用状态机。模型负责选择策略，工具执行受限能力，宿主控制权限、patch 原子性、终止条件和最终验证。", "",
        "## 边界与条件", "",
        "Capability probe 检查原生工具调用和读取 observation；失败不会进入正式 loop。工具只执行能力，模型选择策略。patch 原子作用于内存；默认 dry-run；只有显式授权且宿主 PASS 才写盘，写后失败触发 snapshot rollback。", "",
        "同一模型、模型身份、环境、冻结 source/requirement/tests、每次调用生成参数；最终验证都调用 M6 的包/API/执行/pytest 和 regression guard。one-shot 返回一次完整代码，loop 选择原生工具。初始诊断/提示格式不同，loop 可花更多总调用/token，不是等总预算或纯架构因果实验。每组正式期限 120 秒，独立最终验证另给最多 30 秒。", "",
        "数据：10 个手工设计困难案例、5 个正确 control、5 个安全案例、4 个生命周期案例。手工缺陷不是自然模型失败。正式运行前冻结 manifest；参考解不提供给真实模型，不按运行结果删案例。安全/rollback 挑战由确定性基础设施驱动，单独报告。", "",
        "## 同模型结果", "",
        "| Case | One-shot | First loop repair | Final loop | Steps | Patches | Termination | Rescued |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |"]
    for case in sorted({r["case_id"] for r in rows}):
        a, b = pairs.get((case, "one-shot"), {}), pairs.get((case, "loop"), {})
        detail = strict_rescue(a, b)
        lines.append(f"| {case} | {a.get('status','NOT_RUN')} | {detail['first_repair_status']} | {b.get('status','NOT_RUN')} | {len(b.get('trajectory',[]))} | {b.get('patch_count',0)} | {b.get('termination_reason','NOT_RUN')} | {detail['rescued']} |")
    rescue = summary["strict_rescue"]
    lines += ["", f"严格多轮救回 **{fraction(rescue)}**。原始 same-model one-shot 失败数：{summary['one_shot_failure_count']}。",
        "分母仅为 same-model one-shot 修复失败且成功进入原生协议的困难案例。0/0 表示没有可评估分母，不是 0% 的能力结论。", "",
        "## 核心指标", "", "| 指标 | 分子/分母 |", "| --- | --- |"]
    for name in ["tool_protocol", "patch_acceptance", "false_success"]:
        lines.append(f"| {name} | {fraction(summary[name])} |")
    for condition, result in summary["conditions"].items():
        lines += [f"| {condition} true_pass | {fraction(result['true_pass'])} |",
                  f"| {condition} hard_pass | {fraction(result['hard_pass'])} |",
                  f"| {condition} controls unmodified | {fraction(result['controls_unmodified'])} |",
                  f"| {condition} control preservation | {fraction(result['controls'])} |"]
    for name, value in summary["infrastructure_only"].items():
        lines.append(f"| infrastructure only: {name} | {fraction(value)} |")
    lines += ["", "Control preservation 要求流程最终通过且从未修改候选；controls unmodified 仅回答有没有不必要修改。probe 失败的 control 可以保持原样、独立检查仍通过，但不会被记为流程 PASS。",
        f"全部真实运行源/测试原始哈希不变：{summary['all_live_inputs_unchanged']}。",
        "", "## 成本与失败分类", "", "```json", json.dumps({
        "costs": {k: v["cost"] for k,v in summary["conditions"].items()},
        "probe_failures": summary["probe_failures"], "patch_failures": summary["patch_failures"],
        "not_run": summary["not_run"]}, indent=2, ensure_ascii=False), "```", "",
        "成本包含 probe 调用和最终独立验证；step 仅为正式 loop 步骤，one-shot 没有工具轨迹。token 缺失为 null；样本不足 20 时不报 p95。逐例原始 verification_count 指正式 loop 工具调用数；cases.jsonl 的 validation_counts 从原始证据分别计算初始、正式和最终宿主验证次数，避免漏计。每例 patch_count、latency 和 token 在 JSON 中。", "",
        "## 代表性轨迹", ""]
    for row in rows:
        if row.get("condition") == "one-shot" and row.get("status") == "FAIL":
            error = row.get("final_verification", {}).get("checks", {}).get("run_pytest", {}).get("evidence", {}).get("execution", {}).get("error_type")
            lines.append(f"真实失败案例 [{row['case_id']}](one-shot_{row['case_id']}.json)：最终 pytest {error or '未通过'}；完整失败断言、候选和诊断在原始 artifact。")
    rescued = [b for (case,c),b in pairs.items() if c == "loop" and strict_rescue(pairs.get((case,"one-shot"),{}),b)["rescued"]]
    lines.append(f"真实严格救回轨迹数量：{len(rescued)}。不足两条时不补造；下面的 scripted 演示不计入修复率。")
    choices = rescued[:2] + [r for r in rows if r.get("condition") == "loop" and r.get("status") not in {"PASS","NO_REPAIR_NEEDED"}][:1]
    choices += [r for r in infra if r["case_id"] in {"mean_edges","json_names","patch_format","patch_atomic"}]
    for number, row in enumerate(choices):
        trace = [{"step": s["step"], "decision_summary": s.get("decision_summary", ""),
                  "tool": (s.get("tool_call") or {}).get("name"), "observation": s.get("observation"),
                  "candidate_version": s.get("candidate_version"), "result": s["tool_result"]["status"]}
                 for s in row.get("trajectory", [])]
        name = f"trajectories/{number}_{row['case_id']}.json"
        save(root/name, {"case": row["case_id"], "mode": row.get("mode"), "trajectory": trace,
                        "refusal": row.get("tool_result"), "capability_probe": row.get("capability_probe")})
        lines.append(f"- [{row['case_id']} / {row.get('mode')}]({name})：{row.get('status')}，只含公开摘要与 observation。")
    if sanity:
        s = summary["engineering_sanity"]
        lines += ["", "## Engineering sanity 回归", "",
                  f"模式 {s['mode']}：修复通过 {s['repairs_passed']}/8；control 保持 {s['controls_preserved']}/2；输入哈希不变 {s['all_inputs_unchanged']}。",
                  "该集合历史 one-shot 已 8/8 成功，只用于回归，不进入严格救回分母。模型/runtime/生成参数在 sanity summary 中；历史 controlled evaluation 是不同分布和预算的背景结果，不合并计算。"]
    lines += ["", "## 限制", "", "subprocess、临时目录和 timeout 不是安全沙箱，只适合受控评估。当前是单文件受控修复，不是完整仓库级编码 Agent。Qwen2.5-Coder 7B 保留为原 one-shot baseline；ScriptedTestModel 只验证基础设施。不同模型不能直接归因于 Agent 架构。可见小测试集、手工案例、单次采样、保守 AST 和启发式 regression guard 都限制结论。", "",
        "没有真实云凭据时标记 NOT_RUN_NO_CREDENTIALS；不借用 scripted 数字。云可变模型标签不能保证不可变版本，需要供应商版本信息。无法出现两条真实救回轨迹时如实保留缺项。", "",
        "机器来源：run_manifest.json（配置/环境/模型/哈希）、逐例 JSON（完整原始结果）、cases.jsonl、summary.json。命令见 docs/M7.md。", ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    for path in (root, infrastructure, sanity):
        if path:
            inventory(path)
    return summary
