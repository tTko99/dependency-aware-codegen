from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from typing import Any


def precision_recall_f1(
    expected_positive: Iterable[str], observed_positive: Iterable[str]
) -> dict[str, float | int]:
    expected = Counter(expected_positive)
    observed = Counter(observed_positive)
    labels = expected.keys() | observed.keys()
    true_positive = sum(min(expected[label], observed[label]) for label in labels)
    false_positive = sum(max(0, observed[label] - expected[label]) for label in labels)
    false_negative = sum(max(0, expected[label] - observed[label]) for label in labels)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def aggregate_detection(records: list[dict[str, Any]], key: str) -> dict[str, float | int]:
    expected: list[str] = []
    observed: list[str] = []
    for record in records:
        expected.extend(record.get(f"expected_invalid_{key}", []))
        observed.extend(record.get(f"observed_invalid_{key}", []))
    return precision_recall_f1(expected, observed)


def rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def wilson_interval(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> dict[str, float | int]:
    if total == 0:
        return {"successes": successes, "total": total, "low": 0.0, "high": 0.0}
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return {
        "successes": successes,
        "total": total,
        "low": max(0.0, center - margin),
        "high": min(1.0, center + margin),
    }
