from __future__ import annotations

from typing import Any, Protocol

from depguard.schemas import RepairContext


class CodeGenerator(Protocol):
    model_name: str
    generation_config: dict[str, Any]

    def generate(self, requirement: str) -> str:
        ...


class CodeRepairModel(Protocol):
    model_name: str
    generation_config: dict[str, Any]

    def repair(self, context: RepairContext) -> str:
        ...
