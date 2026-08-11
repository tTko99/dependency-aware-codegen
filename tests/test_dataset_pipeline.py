from typing import Any

from training.prepare_dataset import apply_mutation, audit_leakage, stratified_group_split


def _example(identifier: str, mutation_type: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "leakage_group": identifier,
        "target": f"result = {identifier!r}\n",
        "buggy_code": f"result = 'buggy_{identifier}'\n",
        "metadata": {
            "mutation_type": mutation_type,
            "source_sha256": f"source-{identifier}",
            "buggy_sha256": f"buggy-{identifier}",
            "source_structure_sha256": f"structure-{identifier}",
            "mutation_signature_sha256": f"mutation-{identifier}",
            "original_api": f"module.api_{identifier}",
        },
    }


def test_ast_mutation_renames_exact_call() -> None:
    mutated = apply_mutation(
        "import math\nresult = math.sqrt(4)\n",
        {
            "operation": "rename_call",
            "target": "math.sqrt",
            "replacement": "square_root",
        },
    )

    assert "math.square_root(4)" in mutated
    assert "math.sqrt" not in mutated


def test_stratified_split_has_no_leakage() -> None:
    examples = [
        _example(f"{mutation_type}-{index}", mutation_type)
        for mutation_type in ("function", "method")
        for index in range(5)
    ]

    splits = stratified_group_split(
        examples,
        seed=42,
        train_ratio=0.6,
        validation_ratio=0.2,
    )

    assert {name: len(records) for name, records in splits.items()} == {
        "train": 6,
        "validation": 2,
        "test": 2,
    }
    assert all(not overlaps for overlaps in audit_leakage(splits).values())


def test_ast_mutation_renames_keyword() -> None:
    mutated = apply_mutation(
        "import json\nresult = json.dumps({'x': 1}, sort_keys=True)\n",
        {
            "operation": "rename_keyword",
            "target": "json.dumps",
            "target_keyword": "sort_keys",
            "replacement": "sort_keyz",
        },
    )

    assert "sort_keyz=True" in mutated
