# Dependency-Aware Hallucination Detection and Repair for LLM-Generated Python Code

This repository is a reproducible AI engineering experiment for detecting and repairing
dependency and API hallucinations in Python code. It combines AST analysis, package/API
verification, executable unit tests, Hugging Face inference, and PEFT LoRA fine-tuning.

It does not claim novelty or state-of-the-art performance. The completed benchmark measures
repair of controlled corruptions, not free-form code-generation quality.

## Implemented Pipeline

- Extract imports, aliases, API references, receiver types, and call arguments from Python ASTs.
- Verify packages through import metadata and APIs through resolution, reflection, close
  matches, and conservative signature binding.
- Execute candidates and pytest tests in isolated subprocesses with timeouts.
- Generate seven controlled corruption types while retaining valid target code and mutation
  metadata.
- Validate every source and corruption, split by template/API identity, and audit multiple
  leakage fingerprints.
- Run deterministic Hugging Face inference with a configurable base model and optional LoRA
  adapter.
- Save per-case predictions, manifests, aggregate metrics, confidence intervals, and failure
  analyses as JSON/CSV.

## Model And Environment

The completed experiment uses
[Qwen/Qwen2.5-Coder-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct),
an Apache-2.0 0.49B-parameter Code LLM. The recorded model commit is
`ea3f2471cf1b1f0db85067f1ef93848e38e88c25`.

Runs completed locally on Windows with Python 3.13.8, PyTorch 2.13.0, Transformers 5.15.0,
PEFT 0.20.0, Datasets 5.0.0, and CPU float32 execution. The model remains configurable in the
YAML files under `configs/`. A 1.5B comparison was not run because this machine is CPU-only;
the 0.5B model was retained so all controlled training and held-out evaluation could finish.

Install the project with:

```bash
python -m pip install -e ".[dev]"
```

The checked-in experiment configs use `local_files_only: true` after the model is cached.

## Expanded Dataset

The expanded catalog contains 70 unique API templates rendered with eight parameter variants,
for 560 validated corruption/target pairs. It covers 20 Python library or module families,
including NumPy, pandas, Requests, SciPy, PyYAML, python-dateutil, and common standard-library
modules.

The seven balanced corruption types are:

- hallucinated package
- hallucinated module
- hallucinated class
- hallucinated function
- hallucinated method or attribute
- incorrect argument name
- incorrect argument count or signature

Rebuild it with:

```bash
python -m training.generate_expanded_catalog \
  --output data/raw/expanded_api_examples.jsonl \
  --variants 8

python -m training.prepare_dataset \
  --input data/raw/expanded_api_examples.jsonl \
  --output-dir data/processed/expanded_v2 \
  --seed 42 \
  --train-ratio 0.5 \
  --validation-ratio 0.2 \
  --controls-per-group 2 \
  --small-train-groups-per-type 2
```

The completed build produced 280 train, 112 validation, and 168 held-out test corruptions.
Every valid source passed its test and every mutation failed before repair. Validation and test
benchmarks add 28 and 42 valid controls, giving 140 and 210 total cases respectively.

### Leakage Control

All eight variants of a template remain in one split. Train, validation, and test contain 35,
14, and 21 independent templates. The build found no cross-split overlap for:

- leakage/template group IDs
- exact valid target hashes
- exact corrupted-code hashes
- normalized AST structural fingerprints
- original API identities
- mutation signatures

The exact split IDs, hashes, distributions, and empty overlap sets are recorded in
[`dataset_manifest.json`](results/controlled_api_repair_v2/dataset_manifest.json). The 168 test
rows include correlated variants within 21 templates; Wilson intervals below are row-level and
should be read alongside both row and template counts.

## LoRA Experiments

Three CPU experiments changed only training-set size and adapter rank. All used one epoch,
learning rate `5e-4`, seed 42, batch size 1, gradient accumulation 4, dropout 0.05, and
`q_proj`/`v_proj` targets. Compact repair prompts had zero truncations at 320 tokens.

| Experiment | Train rows | Rank / alpha | Train loss | Validation loss | Validation repairs | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Small R4 | 112 | 4 / 8 | 0.09972 | 0.14371 | 32/112 (28.57%) | 345.2 s |
| Full R4 | 280 | 4 / 8 | 0.07341 | 0.11715 | 53/112 (47.32%) | 607.1 s |
| Full R8 | 280 | 8 / 16 | 0.04683 | 0.14238 | 62/112 (55.36%) | 605.1 s |

The full rank-8 adapter was selected by validation unit-test pass rate before examining its test
performance. Its higher validation loss than full rank 4 is reported rather than hidden; token
loss and executable correctness ranked these adapters differently. The selected adapter has
540,672 trainable parameters and is saved at `checkpoints/expanded_full_r8_e1/adapter`.

Run an experiment with:

```bash
python -m training.train_lora --config configs/experiments/lora_full_r8_e1.yaml
```

Actual training manifests, loss histories, validation predictions, and the selection table are
under [`results/controlled_api_repair_v2/lora_experiments`](results/controlled_api_repair_v2/lora_experiments)
and in
[`lora_experiment_comparison.json`](results/controlled_api_repair_v2/lora_experiment_comparison.json).

## Held-Out Benchmark

The benchmark uses the 168 corrupted test cases plus 42 valid controls. All conditions share the
same model revision, test data, environment, prompt format, detector settings, seed 42, greedy
decoding, and 64-token output cap. Execution errors are measured but do not trigger repair.

- A, `raw_base`: execute the corrupted candidate without repair.
- B, `package_only_generic`: package detection plus base-model repair.
- C, `api_aware_generic`: package/API evidence plus base-model repair.
- D, `api_aware_lora`: the same evidence and prompt as C with the selected LoRA adapter.

| Condition | Syntax valid | Unit tests / execution | 95% Wilson CI | Successful attempts | All required repairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| A. Raw candidate | 210/210 (100.00%) | 42/210 (20.00%) | 15.15-25.93% | n/a | 0/168 |
| B. Package-only + generic | 186/210 (88.57%) | 42/210 (20.00%) | 15.15-25.93% | 0/24 (0.00%) | 0/168 |
| C. API-aware + generic | 144/210 (68.57%) | 77/210 (36.67%) | 30.44-43.37% | 35/160 (21.88%) | 35/168 (20.83%) |
| D. API-aware + LoRA | 202/210 (96.19%) | 127/210 (60.48%) | 53.73-66.84% | 85/160 (53.13%) | 85/168 (50.60%) |

For attempted repairs, C has a 95% Wilson interval of 16.17-28.90% and D has an interval of
45.41-60.69%. In this experiment LoRA does outperform generic repair, but the result is limited
to this controlled, template-generated benchmark and one training seed.

Run one condition with:

```bash
python -m evaluation.run_benchmark \
  --config configs/evaluation_expanded_selected.yaml \
  --method api_aware_lora
```

The consolidated table is
[`comparison.json`](results/controlled_api_repair_v2/test/comparison.json). Per-case outputs,
summary JSON/CSV, resolved config manifests, and SHA-256 dataset hashes are in the same directory.

## Detector Results

On the held-out benchmark, package detection recorded 24 true positives, 0 false positives, and
0 false negatives: precision, recall, and F1 were all 1.00. API detection recorded 136 true
positives, 0 false positives, and 8 false negatives: precision 1.00, recall 0.9444, and F1
0.9714. The 42 valid controls produced no detector false positives.

All eight API misses were incorrect keyword arguments on `datetime.datetime.isoformat`, whose
built-in signature was not inspectable through the current reflection path. These controlled
results do not establish perfect precision on arbitrary dynamic Python code.

## Failure Analysis

The selected LoRA adapter repaired all 24 module corruptions, 16/24 function corruptions,
16/24 method/attribute corruptions, 8/24 class corruptions, 8/24 package corruptions, 8/24
argument-name corruptions, and 5/24 argument-count corruptions.

Its 83 remaining corrupted-case failures were classified as:

| Failure category | Count |
| --- | ---: |
| Unresolved API | 40 |
| Unresolved package | 16 |
| Unit-test failure after a syntactically valid repair | 11 |
| Repaired-code syntax error | 8 |
| Repair not triggered because of detector false negative | 8 |

The generic API-aware model left 133 failures, including 66 repaired-code syntax errors and 36
unresolved APIs. LoRA therefore improved both output discipline and functional correction, but
argument signatures, unseen class/package mappings, and detector coverage remain the main gaps.
Full case-level reports and repair diagnostics are saved as `*_failure_analysis.json` and
`*_repair_diagnosis.json` under `results/controlled_api_repair_v2/test`.

## Why The Pilot LoRA Failed

The first milestone-two LoRA run had only 18 training and 6 validation records. A post-run token
audit found that 9/24 train/validation examples exceeded its 384-token limit (maximum 452), so
the tokenizer dropped left-side prompt context. It also exposed very few APIs per corruption
type. The likely result was learning output form and syntax without enough examples or retained
context to learn semantic repairs.

The expanded compact prompts are 184-283 tokens across train/validation (median 220), with zero
truncations. Increasing the rank-4 training set from 112 to 280 rows raised validation repair
success from 32/112 to 53/112; rank 8 reached 62/112. These observations diagnose the pilot as
data/context limited, but they do not prove that the 0.5B base model is not capacity limited.

## Verification

```bash
python -m ruff check .
python -m pytest -q
```

The tests cover analysis, verification, execution classification, repair orchestration,
occurrence-aware metrics, confidence intervals, AST mutations, and leakage-safe splitting.

## Completed And Planned Work

Completed: 560 validated examples, strict template/API-disjoint splits, detector evaluation,
three real CPU LoRA runs, validation-only adapter selection, controlled A-D held-out evaluation,
confidence intervals, raw counts, and failure analysis.

Planned but not reported as completed: repeated training seeds, externally sourced and licensed
examples, template-cluster confidence intervals, a free-form generation benchmark, independent
detector annotations, and a 1.5B model comparison.

## Limitations

- The examples are programmatically generated from 70 curated templates rather than sampled
  from production code.
- Parameter variants within a template are correlated even though no template crosses splits.
- Detector precision is measured against controlled labels and 42 valid controls.
- Reflection can miss or misclassify lazy attributes, monkey patches, optional dependencies,
  and C-extension signatures.
- The Windows subprocess runner is a timeout boundary, not a hardened security sandbox.
