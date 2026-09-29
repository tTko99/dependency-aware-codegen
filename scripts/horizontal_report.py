"""Report all frozen attempts by provenance and task type without selecting outcomes."""

import json

from evaluation.agent_benchmark import sha
from evaluation.external_report import aggregate, fraction, trajectory
from evaluation.interview_benchmark import save, verify_manifest
from evaluation.interview_metrics import real_pass
from scripts.horizontal_prepare import DATA
from scripts.horizontal_run import OUTPUT, verify


def grouped(cases, rows, key):
    groups = {}
    labels = sorted({key(c) for c in cases})
    for label in labels:
        selected = [c for c in cases if key(c) == label]
        ids = {c["id"] for c in selected}
        groups[label] = aggregate(selected, [r for r in rows if r["case_id"] in ids])
    return groups


def load_rows(frozen):
    index = json.loads((OUTPUT / "run_manifest.json").read_text(encoding="utf-8"))
    if index["freeze_id"] != frozen["freeze_id"]:
        raise ValueError("Run identity mismatch")
    rows = []
    for filename, digest in index["artifact_hashes"].items():
        data = (OUTPUT / "cases" / filename).read_bytes()
        if sha(data) != digest:
            raise ValueError("Case artifact changed")
        row = json.loads(data)
        if row["comparison_identity"] != frozen["freeze_id"]:
            raise ValueError("Case comparison identity mismatch")
        rows.append(row)
    return rows


def report():
    frozen = verify()
    cases = verify_manifest(DATA / "manifest.json")["cases"]
    rows = load_rows(frozen)
    summary = {
        "freeze_id": frozen["freeze_id"],
        "model_identity": frozen["model_identity"],
        "overall_descriptive_only": aggregate(cases, rows),
        "by_source": grouped(cases, rows, lambda c: c["provenance"]["kind"]),
        "by_category": grouped(cases, rows, lambda c: c["category"]),
        "historical_external_summary": "../external_eval_v1/summary.json",
        "interpretation": "Artificial and public adaptations are separate evidence. No real-user success rate or equal-compute causal claim.",
    }
    verification = OUTPUT / "verification.json"
    if verification.exists():
        summary["engineering_verification"] = json.loads(verification.read_text(encoding="utf-8"))
    save(OUTPUT / "summary.json", summary)
    (OUTPUT / "cases.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    lines = [
        "# 横向扩展：冻结混合来源评估",
        "",
        "本轮只新增任务，Agent、提示词、工具边界、验证政策和原有指标定义保持不变。",
        "40个缺陷任务包括4个公开库缺陷适配和36个人工场景；另有10个同源正确对照。",
        "公开部分来自more-itertools的4个不同函数缺陷，保留发行版源码、SHA-256和许可；不等于完整仓库修复。",
        "人工场景在模型运行前编写，明确标注构造来源；不能当作真实用户缺陷。",
        "正式测试对两组可见，没有独立隐藏测试或人工接受率；公开代码也可能进入预训练。",
        "正确对照与错误版本同源，不作为额外独立缺陷。",
        "",
        "## 按来源报告",
        "",
        "| 来源 | 缺陷数 | 单次修复通过 | Agent通过 | Agent正确对照保持 | 严格救回 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for source, s in summary["by_source"].items():
        lines.append(
            f"| {source} | {s['repair_cases']} | {fraction(s['conditions']['one-shot']['repair_pass'])} | "
            f"{fraction(s['conditions']['loop']['repair_pass'])} | {fraction(s['conditions']['loop']['controls_preserved'])} | {fraction(s['strict_rescue'])} |"
        )
    lines += [
        "",
        "## 按类别报告",
        "",
        "| 类别 | 缺陷数 | 单次修复通过 | Agent通过 |",
        "| --- | ---: | --- | --- |",
    ]
    for category, s in summary["by_category"].items():
        lines.append(
            f"| {category} | {s['repair_cases']} | {fraction(s['conditions']['one-shot']['repair_pass'])} | "
            f"{fraction(s['conditions']['loop']['repair_pass'])} |"
        )
    overall = summary["overall_descriptive_only"]
    lines += [
        "",
        "## 协议、补丁与成本",
        "",
        f"所有计划尝试是否有记录：{overall['complete']}；输入哈希未改变：{overall['all_inputs_unchanged']}。",
        f"任务probe {fraction(overall['task_probe'])}；正式工具协议 {fraction(overall['tool_protocol'])}；模型虚假成功 {fraction(overall['false_success_all_tasks'])}。",
        f"接受补丁 {fraction(overall['patch_acceptance'])}；拒绝提前finish {overall['rejected_finish_count']}次。",
        "```json",
        json.dumps(overall["patch_failures"], indent=2),
        "```",
        "",
        "| 条件 | 修复数 | 平均步骤 | 平均模型调用（含任务probe） | 平均秒数 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for condition, s in overall["conditions"].items():
        c = s["cost_repairs"]
        lines.append(
            f"| {condition} | {c['runs']} | {c['mean_steps']} | {c['mean_model_calls']} | {c['mean_seconds']} |"
        )
    lines += [
        "",
        "## 配对结果",
        "",
        "```json",
        json.dumps(overall["paired_repair_outcomes"], indent=2),
        "```",
        "",
        "这只是当前混合样本的描述，不按人为混合比例推断实际用户分布。",
        "原29例QuixBugs结果单独保留；累计覆盖69个未用于控制逻辑调试的缺陷任务，但不把不同来源合并成生产成功率。",
        "旧15例是开发中使用过的回归集，不扩大独立缺陷分母。",
        "",
        "## 所有未通过任务",
        "",
        "| 案例 | 条件 | 状态 | 终止原因 |",
        "| --- | --- | --- | --- |",
    ]
    for r in rows:
        if not real_pass(r):
            lines.append(
                f"| {r['case_id']} | {r['condition']} | {r['status']} | {r['termination_reason']} |"
            )
    selected = {}
    for row in rows:
        if row["condition"] != "loop" or row["is_control"]:
            continue
        steps = row.get("trajectory", [])
        if not real_pass(row):
            selected.setdefault("failure", row)
        if row.get("rejected_finish_count") and real_pass(row):
            selected.setdefault("finish_recovery", row)
        if any(
            (s.get("tool_call") or {}).get("name") == "apply_patch"
            and s["tool_result"]["status"] != "success"
            for s in steps
        ):
            selected.setdefault(
                "patch_rejected_then_pass" if real_pass(row) else "patch_rejected_failure", row
            )
        detail = overall["strict_rescue_details"].get(row["case_id"], {})
        if detail.get("rescued"):
            selected.setdefault("strict_rescue", row)
        if detail.get("first_repair_status") == "FAIL" and real_pass(row):
            selected.setdefault("later_repair", row)
        if real_pass(row):
            selected.setdefault("success", row)
    for label, row in selected.items():
        save(OUTPUT / "trajectories" / f"{label}.json", trajectory(row))
    save(
        OUTPUT / "trajectory_selection.json",
        {
            "observed": {k: r["case_id"] for k, r in selected.items()},
            "not_observed": [
                k
                for k in ("failure", "strict_rescue", "later_repair", "finish_recovery")
                if k not in selected
            ],
        },
    )
    lines += [
        "",
        "## 运行条件与检查",
        "",
        "```json",
        json.dumps(frozen["model_identity"], indent=2),
        "```",
        "",
        "纯本地Ollama；context16384，temperature0，seed42，每次最多2048输出tokens；24步、300秒，最终审核另30秒；工具执行10秒。",
        "相同需求、输入、正式测试、初始诊断格式与宿主验收；两组总调用/token预算不相等。",
        "每例每条件一次，先后交替；不根据模型结果更换任务或调参。",
        "```json",
        json.dumps(
            summary.get("engineering_verification", {"status": "not recorded"}),
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        "参考说明：docs/HORIZONTAL_EVALUATION_PLAN.md；来源及预检：data/horizontal_eval_v1；完整逐例记录：cases.jsonl；冻结凭据：freeze.json。",
        "安全限制仍是保守静态检查与进程/时间边界，不能视为安全沙箱。",
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
    print(
        json.dumps(
            {
                k: {c: v["repair_pass"] for c, v in s["conditions"].items()}
                for k, s in summary["by_source"].items()
            }
        )
    )


if __name__ == "__main__":
    report()
