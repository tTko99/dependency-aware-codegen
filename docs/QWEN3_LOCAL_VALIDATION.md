# 本地 Qwen3-Coder 30B 实证复核

正式报告与机器结果位于 `results/qwen3_validation/report.md` 和 `summary.json`。
该目录保留每次隔离 probe、两个不同评估上下文的 smoke、冻结 manifest、15 对正式结果和安全回归。
smoke 是阶段门禁，不进入正式模型指标；历史 7B 输出保留在原目录。

## 本次实现

- `models/tool_protocol.py`：仅解析原生 `message.tool_calls`，兼容 object / JSON 字符串参数，保留 call ID 和可选 function index。
- `models/agent.py`、`agent/context.py`：`/api/chat` 使用正式 tools schema；observation 用 `role=tool`、`tool_name` 和 call ID 关联回传。
- `agent/probe.py`：三次隔离动作（echo、读取 challenge 后 echo、finish），记录 response model、原始参数类型、ID、observation 和终止原因。probe 不接收 AgentState，也不使用真实工具。
- `agent/contracts.py`、`agent/loop.py`：外部 state 增加初始证据的模型可见投影；不允许旧证据授权新候选。
- `evaluation/interview_benchmark.py`：新配置 `shared_initial_evidence=true` 为两组提供相同格式的宿主初检证据；旧配置默认行为不变。
- `evaluation/interview_metrics.py`：增加 probe 成功率；严格救回须有成功原生 finish 证据。
- `evaluation/local_agent_validation.py`、`local_validation_report.py`：分阶段门禁与可重复派生的报告。

原生工具消息格式依据 [Ollama 官方工具调用说明](https://docs.ollama.com/capabilities/tool-calling)。不解析 content 中的 JSON、XML 或 Markdown 来伪造工具调用。

## 复现顺序（PowerShell）

不要覆盖已有证据。以下路径使用一个新的 RUN 目录；所有推理只连接 localhost。

```powershell
$env:PYTHONPATH='src'
& "$env:LOCALAPPDATA/Programs/Ollama/ollama.exe" ps
# 仅在 7B 仍驻留时执行 stop，不删除历史模型：
# & "$env:LOCALAPPDATA/Programs/Ollama/ollama.exe" stop qwen2.5-coder:7b
.venv/Scripts/python.exe -m evaluation.local_agent_validation probe --output results/RUN/probe_fair.json
.venv/Scripts/python.exe -m evaluation.local_agent_validation smoke --probe-artifact results/RUN/probe_fair.json --output results/RUN/smoke_fair.json
# 确认完整 probe 与 smoke 通过后：
.venv/Scripts/python.exe -m evaluation.interview_benchmark freeze-config --config configs/m7_qwen3_30b.json --output-dir results/RUN/frozen
.venv/Scripts/python.exe -m evaluation.interview_benchmark one-shot --manifest results/RUN/frozen/manifest.json --config configs/m7_qwen3_30b.json --output-dir results/RUN/existing
.venv/Scripts/python.exe -m evaluation.interview_benchmark loop --manifest results/RUN/frozen/manifest.json --config configs/m7_qwen3_30b.json --output-dir results/RUN/existing
.venv/Scripts/python.exe -m evaluation.interview_benchmark infrastructure --output-dir results/RUN/infrastructure
.venv/Scripts/python.exe -m evaluation.local_validation_report --root results/RUN
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check .
```

正式比较支持按已校验 artifact 恢复：同一模型 digest、配置、数据、环境必须一致。不得删除失败 artifact 后选择性重跑。原 one-shot CLI 不变，参见 README。

## 输出契约

- `probe_fair.json`：每步 `response_model`、`argument_type`、`tool_call_id`、`tool_call.function_index`、`observation`、`termination_reason`；含实际加载情况。
- `smoke_fair.json`：完整真实 smoke；报告从其 state_transition 独立检查版本增加、旧检查失效、当前 pytest、finish 和输入完整性。
- `existing/run_manifest.json`：精确模型 digest、Ollama 版本、环境、resolved config、冻结输入 manifest 哈希和逐例 artifact 哈希。
- `cases.jsonl`：完整逐例数据和 formal/initial/final validation_counts、strict_rescue 证据。
- `summary.json`：各项分子、分母、rate；无分母的 rate 为 null。
- `trajectories/`：只展示公开 decision summary、工具、observation 摘要、候选版本、结果；完整 stdout/stderr 在逐例原始 JSON。
- `checks.json`、`runtime_final.json`：回归/lint/完整性检查和最后模型驻留状态。
- `artifact_inventory.json`：生成文件的 SHA-256 清单。

## 验收边界

finish 提交成功声明后，即使外部补做检查通过，也不会反向将缺少当时证据的正式 FAIL 升为 PASS。报告中的虚假成功包含这种提前 finish。
`weights` 如首次 Agent patch 已通过，不满足“首次候选仍失败、读取新 observation、再次不同 patch”的严格救回条件。

默认 dry-run，内存 patch 不修改输入；安全与 rollback 指标来自明确标记的基础设施回归，不是模型能力。临时目录、subprocess、timeout 不是安全沙箱。可见小型单文件测试不证明泛化能力。
