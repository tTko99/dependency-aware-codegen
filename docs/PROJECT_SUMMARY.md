# Project Summary

## Goal

Dependency-Aware Hallucination Detection and Repair is a CLI-first AI engineering system for checking and repairing LLM-generated Python. It accepts an external `.py` file and requirement, performs deterministic AST/package/API validation, runs the program with an optional pytest file, and gives one structured repair request to local Qwen2.5-Coder 7B only when needed. The repaired code is revalidated and re-executed; the original file is never modified.

## Final Architecture

```text
External Python + requirement
  → AST and alias analysis
  → package/API verification
  → controlled execution / unit test
  → structured failure evidence
  → one Qwen2.5-Coder 7B repair
  → revalidation
  → re-execution
  → PASS / FAIL
```

Clean inputs return `NO_REPAIR_NEEDED`, which is a successful outcome. Failed repairs retain their detector and execution evidence; there is no automatic second model round.

## Model Evolution

The project first used Qwen2.5-Coder 0.5B on CPU to validate the controlled repair approach. LoRA improved this weak baseline from 35/160 to 85/160 successful attempted repairs, demonstrating task adaptation with PyTorch, Hugging Face, and PEFT. The practical system then moved to generic Qwen2.5-Coder 7B through Ollama, where 7B fine-tuning was no longer justified by the observed cost/benefit.

## Measured Evidence

| Condition | Final pass | Successful attempted repairs |
| --- | ---: | ---: |
| Raw candidate | 42/210 | n/a |
| 0.5B API-aware generic | 77/210 | 35/160 |
| 0.5B API-aware LoRA | 127/210 | 85/160 |
| 7B API-aware generic | 197/210 | 155/160 |

The 7B condition kept 210/210 outputs syntactically valid and preserved 42/42 controls. Its 13 failures split into eight detector misses and five attempted repair failures. This is an engineering system comparison: historical 0.5B used Hugging Face FP32 on CPU; 7B used Ollama Q4_K_M on GPU.

A separate ten-case, manually prepared external-file sanity set passed 10/10: eight one-shot repairs succeeded and two correct controls did not invoke the model. This is workflow evidence, not a statistically representative real-world benchmark.

## Exact CLI Workflow

```powershell
python -m depguard.cli run --config configs/engineering_7b_ollama.yaml --requirement "Describe the required behavior" --code-file path/to/input.py --test-file path/to/test_input.py --output results/run.json
```

The result JSON includes original code, initial findings/execution, repair status and code, post-repair findings/execution, model latency metadata, and `final_status`.

## Current Limitations

- Python single-file tasks are the primary target.
- Dynamic/reflection-heavy APIs can evade verification.
- Semantic correctness depends on useful requirements and tests.
- The Windows subprocess runner is not a hardened production sandbox.
- Package checks depend on the installed environment.
- Controlled corruptions and the small manual sanity set do not reproduce the full distribution of production LLM code.

## Interview Positioning

Present this as a completed deterministic-plus-LLM repair system, not a pure fine-tuning study. The historical LoRA work proves experimental discipline and task adaptation; the final engineering decision is equally important: a generic local 7B model was already strong enough, so further training was deliberately stopped. The next step is explaining the architecture, evaluation boundaries, failures, and cost/benefit decisions clearly—not running another model experiment.
