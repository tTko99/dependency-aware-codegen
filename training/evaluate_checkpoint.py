from __future__ import annotations

import argparse
import json
from pathlib import Path

from depguard.models.hf import HFCausalRepairModel
from depguard.utils.jsonl import read_jsonl
from training.train_lora import format_repair_prompt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--test-path", default="data/processed/repair_test.jsonl")
    parser.add_argument("--output", default="results/lora_predictions.json")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    args = parser.parse_args(argv)

    model = HFCausalRepairModel(
        model_name=args.model_name,
        adapter_path=args.adapter_path,
        max_new_tokens=args.max_new_tokens,
        temperature=0.0,
        top_p=1.0,
        repetition_penalty=1.0,
        device_map="cpu",
        torch_dtype="float32",
        local_files_only=True,
        use_chat_template=True,
    )
    records = read_jsonl(args.test_path)
    predictions = []
    for record in records:
        prompt = record.get("prompt") or format_repair_prompt(record)
        generated = model.generate_from_prompt(prompt)
        predictions.append(
            {
                "id": record.get("id"),
                "buggy_code": record["buggy_code"],
                "target": record["target"],
                "prediction": generated,
            }
        )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(predictions, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
