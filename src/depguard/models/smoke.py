from __future__ import annotations

from typing import Any, ClassVar

from depguard.schemas import RepairContext


class HeuristicSmokeCodeGenerator:
    """Offline smoke generator used only for tests and CLI demonstrations."""

    model_name = "heuristic-smoke-generator"
    generation_config: ClassVar[dict[str, Any]] = {"kind": "heuristic-smoke"}

    def generate(self, requirement: str) -> str:
        lowered = requirement.lower()
        if "square root" in lowered or "sqrt" in lowered:
            return "import math\n\nresult = math.square_root(4)\nprint(result)\n"
        if "json" in lowered:
            return "import json\n\nprint(json.loads('{\"ok\": true}'))\n"
        if "path" in lowered:
            return "from pathlib import Path\n\nprint(Path('.').exists())\n"
        return "print('no-op smoke generation')\n"


class HeuristicRepairModel:
    """Deterministic candidate replacement for smoke tests, not a benchmarked LLM repairer."""

    model_name = "heuristic-repair"
    generation_config: ClassVar[dict[str, Any]] = {"kind": "heuristic-candidate-replacement"}

    def repair(self, context: RepairContext) -> str:
        repaired = context.original_code
        for result in context.api_results:
            if result.api_valid or not result.suggestions:
                continue
            source = result.reference.source
            replacement = self._source_replacement(source, result.suggestions[0])
            if source and replacement and source in repaired:
                repaired = repaired.replace(source, replacement, 1)
                break
        return repaired

    @staticmethod
    def _source_replacement(source: str, canonical_candidate: str) -> str:
        candidate_leaf = canonical_candidate.rsplit(".", maxsplit=1)[-1]
        if "." in source:
            return f"{source.rsplit('.', maxsplit=1)[0]}.{candidate_leaf}"
        return candidate_leaf
