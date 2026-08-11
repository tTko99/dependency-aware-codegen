from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import torch
import transformers
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
    set_seed,
)

from depguard.config import load_config
from depguard.models.chat import format_chat_prompt
from depguard.utils.jsonl import read_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/lora.yaml")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    model_cfg = config["model"]
    data_cfg = config["data"]
    args_cfg = config["training"]
    seed = int(args_cfg.get("seed", 42))
    set_seed(seed)

    train_records = read_jsonl(data_cfg["train_path"])
    validation_records = read_jsonl(data_cfg["validation_path"])
    if not train_records or not validation_records:
        raise ValueError("Training and validation datasets must both be non-empty")

    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["name"],
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
        local_files_only=bool(model_cfg.get("local_files_only", False)),
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {
        "trust_remote_code": bool(model_cfg.get("trust_remote_code", False)),
        "local_files_only": bool(model_cfg.get("local_files_only", False)),
        "low_cpu_mem_usage": True,
    }
    dtype_key = "dtype" if int(transformers.__version__.split(".", maxsplit=1)[0]) >= 5 else "torch_dtype"
    model_kwargs[dtype_key] = _resolve_dtype(model_cfg.get("torch_dtype", "float32"))
    model = AutoModelForCausalLM.from_pretrained(model_cfg["name"], **model_kwargs)
    model.config.use_cache = False
    lora_cfg = config["lora"]
    model = get_peft_model(
        model,
        LoraConfig(
            r=int(lora_cfg["rank"]),
            lora_alpha=int(lora_cfg["alpha"]),
            lora_dropout=float(lora_cfg["dropout"]),
            target_modules=list(lora_cfg["target_modules"]),
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    trainable_parameters, total_parameters = count_parameters(model)
    model.print_trainable_parameters()

    max_length = int(args_cfg["max_sequence_length"])
    raw_train_lengths = [record_token_length(record, tokenizer) for record in train_records]
    raw_validation_lengths = [
        record_token_length(record, tokenizer) for record in validation_records
    ]
    tokenized_train = [tokenize_record(record, tokenizer, max_length) for record in train_records]
    tokenized_validation = [
        tokenize_record(record, tokenizer, max_length) for record in validation_records
    ]
    train_dataset = Dataset.from_list(tokenized_train)
    validation_dataset = Dataset.from_list(tokenized_validation)

    output_dir = Path(args_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = build_training_arguments(args_cfg, output_dir, seed)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer,
            padding=True,
            label_pad_token_id=-100,
            return_tensors="pt",
        ),
    )

    started = time.time()
    train_result = trainer.train()
    eval_metrics = trainer.evaluate()
    trainer.save_state()
    adapter_dir = output_dir / "adapter"
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    metrics = {
        "train": train_result.metrics,
        "validation": eval_metrics,
        "log_history": trainer.state.log_history,
        "wall_time_seconds": time.time() - started,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "base_model": model_cfg["name"],
        "base_model_commit": getattr(model.config, "_commit_hash", None),
        "adapter_path": str(adapter_dir),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "python_version": platform.python_version(),
        "library_versions": {
            package: version(package)
            for package in ("torch", "transformers", "peft", "datasets", "accelerate")
        },
        "config": config,
        "train_records": len(train_records),
        "validation_records": len(validation_records),
        "train_file_sha256": sha256_file(Path(data_cfg["train_path"])),
        "validation_file_sha256": sha256_file(Path(data_cfg["validation_path"])),
        "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters,
        "trainable_percent": 100 * trainable_parameters / total_parameters,
        "sequence_lengths": {
            "max_configured": max_length,
            "train_max": max(len(record["input_ids"]) for record in tokenized_train),
            "validation_max": max(len(record["input_ids"]) for record in tokenized_validation),
            "train_raw_max": max(raw_train_lengths),
            "validation_raw_max": max(raw_validation_lengths),
            "train_truncated_records": sum(
                1 for length in raw_train_lengths if length > max_length
            ),
            "validation_truncated_records": sum(
                1 for length in raw_validation_lengths if length > max_length
            ),
        },
        "metrics_path": str(output_dir / "metrics.json"),
    }
    (output_dir / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    results_dir_value = args_cfg.get("results_dir")
    if results_dir_value:
        results_dir = Path(results_dir_value)
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "training_metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
        )
        (results_dir / "training_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
    print(json.dumps({"manifest": manifest, "metrics": metrics}, indent=2, sort_keys=True))
    return 0


def tokenize_record(record: dict[str, Any], tokenizer: Any, max_length: int) -> dict[str, Any]:
    prompt = record.get("prompt") or format_repair_prompt(record)
    model_prompt = format_chat_prompt(tokenizer, prompt)
    target = record["target"].strip() + tokenizer.eos_token
    prompt_ids = tokenizer(model_prompt, add_special_tokens=False)["input_ids"]
    target_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
    if len(target_ids) >= max_length:
        raise ValueError(f"Target for {record.get('id')} exceeds max_sequence_length")
    max_prompt_length = max_length - len(target_ids)
    if len(prompt_ids) > max_prompt_length:
        prompt_ids = prompt_ids[-max_prompt_length:]
    input_ids = prompt_ids + target_ids
    labels = [-100] * len(prompt_ids) + target_ids
    return {"input_ids": input_ids, "labels": labels, "attention_mask": [1] * len(input_ids)}


def format_repair_prompt(record: dict[str, Any]) -> str:
    return (
        "Repair the generated Python code. Return Python code only.\n\n"
        f"Requirement:\n{record['requirement']}\n\n"
        f"Generated code:\n{record['buggy_code']}\n\n"
        f"Detected error:\n{record.get('error', 'See the invalid dependency/API usage.')}\n"
    )


def record_token_length(record: dict[str, Any], tokenizer: Any) -> int:
    prompt = record.get("prompt") or format_repair_prompt(record)
    model_prompt = format_chat_prompt(tokenizer, prompt)
    target = record["target"].strip() + tokenizer.eos_token
    return len(tokenizer(model_prompt, add_special_tokens=False)["input_ids"]) + len(
        tokenizer(target, add_special_tokens=False)["input_ids"]
    )


def build_training_arguments(
    config: dict[str, Any], output_dir: Path, seed: int
) -> TrainingArguments:
    kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "learning_rate": float(config["learning_rate"]),
        "per_device_train_batch_size": int(config["batch_size"]),
        "per_device_eval_batch_size": int(config.get("eval_batch_size", config["batch_size"])),
        "gradient_accumulation_steps": int(config["gradient_accumulation_steps"]),
        "num_train_epochs": float(config["epochs"]),
        "logging_steps": int(config.get("logging_steps", 1)),
        "logging_first_step": True,
        "save_strategy": config.get("save_strategy", "epoch"),
        "save_total_limit": int(config.get("save_total_limit", 1)),
        "fp16": bool(config.get("fp16", False)),
        "bf16": bool(config.get("bf16", False)),
        "report_to": config.get("report_to", "none"),
        "optim": config.get("optim", "adamw_torch"),
        "dataloader_pin_memory": torch.cuda.is_available(),
        "use_cpu": not torch.cuda.is_available(),
        "seed": seed,
        "data_seed": seed,
    }
    parameters = inspect.signature(TrainingArguments.__init__).parameters
    eval_key = "eval_strategy" if "eval_strategy" in parameters else "evaluation_strategy"
    kwargs[eval_key] = config.get("evaluation_strategy", "epoch")
    return TrainingArguments(**kwargs)


def count_parameters(model: Any) -> tuple[int, int]:
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    return trainable, total


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_dtype(value: str) -> torch.dtype:
    try:
        return getattr(torch, value)
    except AttributeError as exc:
        raise ValueError(f"Unsupported torch dtype: {value}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
