# M7.2：最后一次通用 Agent 行为修正与冻结复测

## Before / after

| 指标 | M7.1 | M7.2 |
| --- | --- | --- |
| Agent 最终通过 | 12/15 (80.0%) | 15/15 (100.0%) |
| 严格多轮救回 | 0/1 (0.0%) | 1/1 (100.0%) |
| control 保持 | 4/5 (80.0%) | 5/5 (100.0%) |
| 虚假成功 / 全部任务 | 3/15 (20.0%) | 0/15 (0.0%) |
| 平均步骤 | 4.933 | 5.600 |
| 平均模型调用数 | 7.933 | 7.600 |
| 平均耗时（秒） | 19.392 | 27.119 |

正式协议（仅触发修复的案例）：10/10 (100.0%)；触发修复 10/15。
正式任务独立 probe：10/10 (100.0%)；运行前完整隔离 probe：passed。
原始指标函数的虚假成功率（成功声明任务为分母）：0/10 (0.0%)。
全部任务分母 15 的虚假成功行按用户要求另列；分子、最终真实 PASS、strict_rescue 函数均未修改。被拒绝但后来验证成功的 finish 不构成最终虚假成功；所有拒绝事件另存。

## 冻结与公平性

复用 `results/qwen3_validation/frozen/manifest.json` 和 `configs/m7_qwen3_30b.json`，均未改写。模型 digest、Ollama 版本、温度 0、context 16384、24 步、300 秒及正式测试/验证规则保持一致。M7.1 所有 artifact 和评估源/测试/reference/config/manifest 的哈希均与运行前一致。
one-shot 原 15 份 artifact 逐字节复用，没有重新推理或选择较好结果。两组 prompt 本来不同；本次仅修改通用控制逻辑/说明与状态 observation，没有案例专用提示。
初检采用同一真实验证工具；正确原始 candidate 直接 NO_REPAIR_NEEDED、agent_invoked=false，不调用模型也不应用 patch。低层 AgentLoop.run 用于已有状态的继续运行；CLI 和 M7.2 使用 run_agent 门禁。
M7.2 的 300 秒上限包含门禁、probe 和 loop；M7.1 初检在 loop 上限之外。修复任务最终独立审核均另限 30 秒；执行工具均 10 秒。未触发修复的 control 复用初检证据。平均成本包含全部 15 例，control 为零模型调用。

## 逐例结果

| 案例 | M7.1 | M7.2 | Agent invoked | 步数 | 接受 patch | finish 拒绝 | 终止 | 严格救回 |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| mean_edges | PASS | PASS | True | 7 | 1 | 0 | finish | False |
| json_names | FAIL | PASS | True | 7 | 1 | 0 | finish | False |
| chunks | PASS | PASS | True | 9 | 1 | 0 | finish | False |
| weights | PASS | PASS | True | 9 | 2 | 0 | finish | True |
| stable_unique | PASS | PASS | True | 7 | 1 | 0 | finish | False |
| flatten | PASS | PASS | True | 11 | 1 | 0 | finish | False |
| merge_counts | PASS | PASS | True | 12 | 1 | 0 | finish | False |
| median | FAIL | PASS | True | 7 | 1 | 0 | finish | False |
| runs | FAIL | PASS | True | 8 | 1 | 1 | finish | False |
| intervals | PASS | PASS | True | 7 | 1 | 0 | finish | False |
| control_mean_edges | PASS | NO_REPAIR_NEEDED | False | 0 | 0 | 0 | no_repair_needed | False |
| control_json_names | PASS | NO_REPAIR_NEEDED | False | 0 | 0 | 0 | no_repair_needed | False |
| control_chunks | PASS | NO_REPAIR_NEEDED | False | 0 | 0 | 0 | no_repair_needed | False |
| control_weights | PASS | NO_REPAIR_NEEDED | False | 0 | 0 | 0 | no_repair_needed | False |
| control_stable_unique | PASS | NO_REPAIR_NEEDED | False | 0 | 0 | 0 | no_repair_needed | False |

## 提前 finish 的实际表现

本轮有 1 个案例收到 FINISH_PRECONDITION_FAILED。

```json
[
  {
    "case_id": "runs",
    "rejected_steps": [
      4
    ],
    "later_actions": [
      {
        "step": 5,
        "tool": "execute"
      },
      {
        "step": 6,
        "tool": "validate_apis"
      },
      {
        "step": 7,
        "tool": "validate_packages"
      },
      {
        "step": 8,
        "tool": "finish"
      }
    ],
    "final_status": "PASS"
  }
]
```

## 真实代表轨迹

- [chunks](trajectories/chunks.json)：PASS；strict rescue=False。
- [weights](trajectories/weights.json)：PASS；strict rescue=True。
- [flatten](trajectories/flatten.json)：PASS；strict rescue=False。
- [merge_counts](trajectories/merge_counts.json)：PASS；strict rescue=False。
- [runs](trajectories/runs.json)：PASS；strict rescue=False。

## 完整指标

```json
{
  "patch_acceptance": {
    "numerator": 11,
    "denominator": 17,
    "rate": 0.6470588235294118
  },
  "patch_failures": {
    "PATCH_PARSE_ERROR": 6
  },
  "cost": {
    "runs": 15,
    "mean_steps": 5.6,
    "median_steps": 7,
    "mean_model_calls": 7.6,
    "mean_seconds": 27.118666666668528,
    "p95_seconds": null,
    "mean_validation_calls": 10.4,
    "p95_policy": "nearest rank; at least 20 completed attempts",
    "input_tokens": 411181,
    "output_tokens": 6602
  },
  "infrastructure_only": {
    "unauthorized_refusal": {
      "numerator": 5,
      "denominator": 5,
      "rate": 1.0
    },
    "rollback": {
      "numerator": 1,
      "denominator": 1,
      "rate": 1.0
    }
  },
  "checks": {
    "pytest": {
      "passed": 241,
      "skipped": 1,
      "failed": 0,
      "skip_reason": "Windows symlink creation privilege",
      "log": "pytest.txt"
    },
    "ruff": {
      "passed": true,
      "log": "ruff.txt"
    },
    "protected_file_count": 149,
    "protected_files_unchanged": true,
    "implementation_frozen_during_run": true,
    "one_shot_reused_byte_for_byte": true,
    "all_source_test_hashes_unchanged": true,
    "all_runs_dry_run": true,
    "native_formal_calls_verified": 84,
    "all_observations_include_validation_state": true,
    "control_zero_model_calls": 5,
    "forbidden_log_fields": [],
    "whitespace_findings": [],
    "git_operations": 0,
    "cloud_model_calls": 0,
    "weights_strict_rescue": {
      "eligible": true,
      "rescued": true,
      "first_repair_status": "FAIL",
      "failure_observation_step": 3,
      "rescued_patch_step": 4
    }
  }
}
```

## 限制与停止条件

这是最后一次通用行为修正；只运行一次正式冻结复测，没有筛掉失败、增加案例或选择性重跑。工具协议、代码通过率与严格多轮收益分别报告。小型可见测试、手工单文件集不能证明泛化；进程、临时目录和 timeout 不是安全沙箱。ScriptedTestModel 只用于基础设施测试。
本轮 Agent 通过 15/15 (100.0%)；复用 one-shot 14/15 (93.3%)。
无论本轮优于、持平还是低于 one-shot，都不再针对该评估集继续优化。没有真实严格救回时如实保留 0。
修改及复现说明见 docs/M7_2.md；checks.json、comparison/run_manifest.json、cases.jsonl、summary.json、protected_before.json 提供复核来源。未执行 Git 操作，未调用云模型。
