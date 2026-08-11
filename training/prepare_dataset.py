from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from depguard.analysis import DependencyAnalyzer
from depguard.execution import SandboxedExecutor
from depguard.pipeline import DependencyGuardPipeline
from depguard.utils.jsonl import read_jsonl, write_jsonl
from depguard.verification import APIVerifier, PackageVerifier


class MutationError(ValueError):
    pass


class ControlledMutator(ast.NodeTransformer):
    def __init__(self, mutation: dict[str, Any]) -> None:
        self.mutation = mutation
        self.applied = 0

    def visit_Import(self, node: ast.Import) -> ast.AST:
        self.generic_visit(node)
        if self.mutation["operation"] != "rename_import":
            return node
        for alias in node.names:
            if alias.name == self.mutation["target"]:
                local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                alias.name = self.mutation["replacement"]
                alias.asname = local_name
                self.applied += 1
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        target = _dotted_name(node.func)
        if target != self.mutation["target"]:
            return node

        operation = self.mutation["operation"]
        if operation == "rename_call":
            if not isinstance(node.func, ast.Attribute):
                raise MutationError("rename_call requires an attribute call target")
            node.func.attr = self.mutation["replacement"]
        elif operation == "replace_arguments":
            node.args = [ast.parse(value, mode="eval").body for value in self.mutation["args"]]
            node.keywords = [
                ast.keyword(arg=name, value=ast.parse(value, mode="eval").body)
                for name, value in self.mutation.get("keywords", {}).items()
            ]
        elif operation == "rename_keyword":
            target_keyword = self.mutation["target_keyword"]
            matching = [keyword for keyword in node.keywords if keyword.arg == target_keyword]
            if len(matching) != 1:
                raise MutationError(
                    f"Expected one keyword {target_keyword} on {target}, found {len(matching)}"
                )
            matching[0].arg = self.mutation["replacement"]
        else:
            return node
        self.applied += 1
        return node


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/api_examples.jsonl")
    parser.add_argument("--output-dir", default="data/processed")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--controls-per-group", type=int, default=2)
    parser.add_argument("--small-train-groups-per-type", type=int, default=2)
    args = parser.parse_args(argv)

    if args.train_ratio <= 0 or args.validation_ratio <= 0:
        raise ValueError("train and validation ratios must be positive")
    if args.train_ratio + args.validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be less than 1")

    source_path = Path(args.input)
    source_records = read_jsonl(source_path)
    if not source_records:
        raise ValueError(f"No source records found in {source_path}")

    executor = SandboxedExecutor(timeout_seconds=args.timeout)
    pipeline = DependencyGuardPipeline(
        analyzer=DependencyAnalyzer(),
        package_verifier=PackageVerifier(),
        api_verifier=APIVerifier(),
        executor=executor,
        enable_api_validation=True,
        enable_execution=True,
        repair_method="dataset",
        repair_on_execution_error=True,
    )

    examples = [build_example(record, pipeline, executor) for record in source_records]
    splits = stratified_group_split(
        examples,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
    )
    leakage = audit_leakage(splits)
    if any(leakage.values()):
        raise ValueError(f"Dataset leakage detected: {leakage}")

    output_dir = Path(args.output_dir)
    for split, records in splits.items():
        write_jsonl(output_dir / f"repair_{split}.jsonl", records)
    small_train = select_small_train_split(
        splits["train"], groups_per_type=args.small_train_groups_per_type
    )
    write_jsonl(output_dir / "repair_train_small.jsonl", small_train)
    benchmark_validation = add_valid_controls(
        splits["validation"], controls_per_group=args.controls_per_group
    )
    benchmark_test = add_valid_controls(
        splits["test"], controls_per_group=args.controls_per_group
    )
    write_jsonl(output_dir / "benchmark_validation.jsonl", benchmark_validation)
    write_jsonl(output_dir / "benchmark_test.jsonl", benchmark_test)

    manifest = build_manifest(
        source_path=source_path,
        source_records=source_records,
        splits=splits,
        leakage=leakage,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
        small_train=small_train,
        benchmark_validation=benchmark_validation,
        benchmark_test=benchmark_test,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def build_example(
    record: dict[str, Any],
    pipeline: DependencyGuardPipeline,
    executor: SandboxedExecutor,
) -> dict[str, Any]:
    required = {"id", "requirement", "valid_code", "test_code", "mutation"}
    missing = sorted(required - record.keys())
    if missing:
        raise ValueError(f"{record.get('id', '<unknown>')}: missing fields {missing}")

    target_code = normalize_code(record["valid_code"])
    valid_result = executor.execute(target_code, test_code=record["test_code"])
    if valid_result.status != "passed":
        raise ValueError(
            f"{record['id']}: valid source failed its test: "
            f"{valid_result.error_type}: {valid_result.stderr[-500:]}"
        )

    buggy_code = apply_mutation(target_code, record["mutation"])
    pipeline_result = pipeline.run(
        requirement=record["requirement"],
        code=buggy_code,
        test_code=record["test_code"],
    )
    if not pipeline_result.execution_result or pipeline_result.execution_result.status == "passed":
        raise ValueError(f"{record['id']}: mutation did not produce an execution failure")
    if not pipeline_result.repair_prompt:
        raise ValueError(f"{record['id']}: mutation did not produce a repair prompt")

    mutation = record["mutation"]
    return {
        "id": record["id"],
        "leakage_group": record.get("leakage_group", record["id"]),
        "template_id": record.get("template_id", record.get("leakage_group", record["id"])),
        "library": record.get("library", "unknown"),
        "instruction": "Repair the generated Python code using the detected dependency evidence.",
        "requirement": record["requirement"],
        "buggy_code": buggy_code,
        "target": target_code,
        "test_code": record["test_code"],
        "prompt": pipeline_result.repair_prompt,
        "expected_invalid_packages": mutation.get("expected_invalid_packages", []),
        "expected_invalid_apis": mutation.get("expected_invalid_apis", []),
        "metadata": {
            "mutation_type": mutation["type"],
            "operation": mutation["operation"],
            "target": mutation["target"],
            "replacement": mutation.get("replacement"),
            "target_keyword": mutation.get("target_keyword"),
            "original_api": mutation.get("original_api", record.get("original_api")),
            "source_sha256": sha256_text(target_code),
            "buggy_sha256": sha256_text(buggy_code),
            "source_structure_sha256": structural_sha256(target_code),
            "mutation_signature_sha256": mutation_signature(mutation),
            "execution_error_type": pipeline_result.execution_result.error_type,
            "execution_error_category": pipeline_result.execution_result.error_category,
        },
    }


def apply_mutation(code: str, mutation: dict[str, Any]) -> str:
    tree = ast.parse(code)
    mutator = ControlledMutator(mutation)
    mutated = mutator.visit(tree)
    if mutator.applied != 1:
        raise MutationError(
            f"Expected exactly one mutation for {mutation['target']}, applied {mutator.applied}"
        )
    ast.fix_missing_locations(mutated)
    result = ast.unparse(mutated).strip() + "\n"
    ast.parse(result)
    if result == code:
        raise MutationError(f"Mutation for {mutation['target']} did not change the code")
    return result


def normalize_code(code: str) -> str:
    return ast.unparse(ast.parse(code)).strip() + "\n"


def stratified_group_split(
    examples: list[dict[str, Any]],
    *,
    seed: int,
    train_ratio: float,
    validation_ratio: float,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        grouped[example["leakage_group"]].append(example)

    groups_by_type: dict[str, list[str]] = defaultdict(list)
    for group, records in grouped.items():
        mutation_types = {record["metadata"]["mutation_type"] for record in records}
        if len(mutation_types) != 1:
            raise ValueError(f"Leakage group {group} spans multiple mutation types")
        groups_by_type[next(iter(mutation_types))].append(group)

    assignments: dict[str, str] = {}
    for mutation_type, groups in sorted(groups_by_type.items()):
        rng = random.Random(f"{seed}:{mutation_type}")
        ordered = sorted(groups)
        rng.shuffle(ordered)
        train_count = max(1, int(len(ordered) * train_ratio))
        validation_count = max(1, int(len(ordered) * validation_ratio))
        if train_count + validation_count >= len(ordered):
            raise ValueError(
                f"Need at least three groups for mutation type {mutation_type}; got {len(ordered)}"
            )
        for index, group in enumerate(ordered):
            if index < train_count:
                assignments[group] = "train"
            elif index < train_count + validation_count:
                assignments[group] = "validation"
            else:
                assignments[group] = "test"

    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    for group, records in grouped.items():
        splits[assignments[group]].extend(records)
    for records in splits.values():
        records.sort(key=lambda item: item["id"])
    return splits


def audit_leakage(splits: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    audits: dict[str, list[str]] = {}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        left_groups = {record["leakage_group"] for record in splits[left]}
        right_groups = {record["leakage_group"] for record in splits[right]}
        audits[f"{left}_{right}_groups"] = sorted(left_groups & right_groups)

        left_targets = {record["metadata"]["source_sha256"] for record in splits[left]}
        right_targets = {record["metadata"]["source_sha256"] for record in splits[right]}
        audits[f"{left}_{right}_targets"] = sorted(left_targets & right_targets)

        left_buggy = {record["metadata"]["buggy_sha256"] for record in splits[left]}
        right_buggy = {record["metadata"]["buggy_sha256"] for record in splits[right]}
        audits[f"{left}_{right}_buggy"] = sorted(left_buggy & right_buggy)

        left_structures = {
            record["metadata"]["source_structure_sha256"] for record in splits[left]
        }
        right_structures = {
            record["metadata"]["source_structure_sha256"] for record in splits[right]
        }
        audits[f"{left}_{right}_structures"] = sorted(left_structures & right_structures)

        left_apis = {record["metadata"].get("original_api") for record in splits[left]}
        right_apis = {record["metadata"].get("original_api") for record in splits[right]}
        audits[f"{left}_{right}_original_apis"] = sorted(
            value for value in left_apis & right_apis if value
        )

        left_mutations = {
            record["metadata"]["mutation_signature_sha256"] for record in splits[left]
        }
        right_mutations = {
            record["metadata"]["mutation_signature_sha256"] for record in splits[right]
        }
        audits[f"{left}_{right}_mutation_signatures"] = sorted(
            left_mutations & right_mutations
        )
    return audits


def build_manifest(
    *,
    source_path: Path,
    source_records: list[dict[str, Any]],
    splits: dict[str, list[dict[str, Any]]],
    leakage: dict[str, list[str]],
    seed: int,
    train_ratio: float,
    validation_ratio: float,
    small_train: list[dict[str, Any]],
    benchmark_validation: list[dict[str, Any]],
    benchmark_test: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_path": str(source_path),
        "source_sha256": sha256_text(source_path.read_text(encoding="utf-8")),
        "seed": seed,
        "ratios": {
            "train": train_ratio,
            "validation": validation_ratio,
            "test": 1 - train_ratio - validation_ratio,
        },
        "source_record_count": len(source_records),
        "split_counts": {split: len(records) for split, records in splits.items()},
        "mutation_counts": {
            split: dict(sorted(Counter(r["metadata"]["mutation_type"] for r in records).items()))
            for split, records in splits.items()
        },
        "split_ids": {split: [record["id"] for record in records] for split, records in splits.items()},
        "small_train_count": len(small_train),
        "benchmark_validation_count": len(benchmark_validation),
        "benchmark_test_count": len(benchmark_test),
        "library_counts": {
            split: dict(sorted(Counter(r["library"] for r in records).items()))
            for split, records in splits.items()
        },
        "independent_template_counts": {
            split: len({record["template_id"] for record in records})
            for split, records in splits.items()
        },
        "leakage_audit": leakage,
        "all_valid_sources_passed": True,
        "all_mutations_failed_execution": True,
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def structural_sha256(code: str) -> str:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            node.value = f"<{type(node.value).__name__}>"
    return sha256_text(ast.dump(tree, annotate_fields=True, include_attributes=False))


def mutation_signature(mutation: dict[str, Any]) -> str:
    fields = {
        key: mutation.get(key)
        for key in (
            "type",
            "operation",
            "target",
            "replacement",
            "target_keyword",
            "original_api",
            "args",
            "keywords",
        )
    }
    return sha256_text(json.dumps(fields, sort_keys=True))


def select_small_train_split(
    records: list[dict[str, Any]], *, groups_per_type: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = (record["metadata"]["mutation_type"], record["leakage_group"])
        groups[key].append(record)
    selected_groups: set[tuple[str, str]] = set()
    for mutation_type in sorted({key[0] for key in groups}):
        candidates = sorted(key for key in groups if key[0] == mutation_type)
        if len(candidates) < groups_per_type:
            raise ValueError(f"Not enough train groups for {mutation_type}")
        selected_groups.update(candidates[:groups_per_type])
    selected = [record for key in selected_groups for record in groups[key]]
    return sorted(selected, key=lambda item: item["id"])


def add_valid_controls(
    records: list[dict[str, Any]], *, controls_per_group: int
) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_group[record["leakage_group"]].append(record)

    controls: list[dict[str, Any]] = []
    for group_records in by_group.values():
        for record in sorted(group_records, key=lambda item: item["id"])[:controls_per_group]:
            control = dict(record)
            control["id"] = f"valid_control_{record['id']}"
            control["buggy_code"] = record["target"]
            control["prompt"] = None
            control["expected_invalid_packages"] = []
            control["expected_invalid_apis"] = []
            control["metadata"] = {
                **record["metadata"],
                "mutation_type": "valid_control",
                "source_mutation_type": record["metadata"]["mutation_type"],
                "buggy_sha256": record["metadata"]["source_sha256"],
            }
            controls.append(control)
    return sorted(records + controls, key=lambda item: item["id"])


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
