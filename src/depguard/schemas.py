from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ErrorCategory(str, Enum):
    HALLUCINATED_PACKAGE = "hallucinated_package"
    HALLUCINATED_MODULE = "hallucinated_module"
    HALLUCINATED_CLASS = "hallucinated_class"
    HALLUCINATED_FUNCTION = "hallucinated_function"
    HALLUCINATED_METHOD_OR_ATTRIBUTE = "hallucinated_method_or_attribute"
    IMPORT_ERROR = "import_error"
    SYNTAX_ERROR = "syntax_error"
    NAME_ERROR = "name_error"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    ATTRIBUTE_ERROR = "attribute_error"
    INCORRECT_ARGUMENTS = "incorrect_arguments"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    WRONG_OUTPUT = "wrong_output"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ImportReference:
    module: str
    name: str | None
    alias: str | None
    line_number: int
    is_from_import: bool
    level: int = 0

    @property
    def canonical_path(self) -> str:
        if self.name:
            return f"{self.module}.{self.name}" if self.module else self.name
        return self.module

    @property
    def package(self) -> str:
        path = self.module or self.name or ""
        return path.split(".", maxsplit=1)[0] if path else ""


@dataclass(frozen=True)
class AliasBinding:
    local_name: str
    canonical_path: str
    import_type: str
    line_number: int


@dataclass(frozen=True)
class APIReference:
    canonical_path: str
    package: str
    module: str
    object_path: str
    call_type: str
    line_number: int
    source: str
    receiver: str | None = None
    arg_count: int | None = None
    keyword_names: tuple[str, ...] = ()
    is_call: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    imports: list[ImportReference]
    alias_table: dict[str, AliasBinding]
    api_references: list[APIReference]
    syntax_error: str | None = None


@dataclass(frozen=True)
class PackageValidationResult:
    package: str
    exists: bool
    status: str
    version: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class APIVerificationResult:
    reference: APIReference
    package_valid: bool
    module_valid: bool
    api_valid: bool
    status: str
    reason: str | None = None
    resolved_module: str | None = None
    suggestions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    return_code: int | None
    stdout: str
    stderr: str
    error_type: str | None
    error_category: str
    execution_time: float
    timed_out: bool = False


@dataclass(frozen=True)
class RepairContext:
    requirement: str
    original_code: str
    package_results: list[PackageValidationResult]
    api_results: list[APIVerificationResult]
    execution_result: ExecutionResult | None
    suspicious_reference: APIReference | None
    candidate_apis: tuple[str, ...]
    repair_method: str


@dataclass(frozen=True)
class PipelineResult:
    requirement: str
    generated_code: str
    analysis: AnalysisResult
    package_results: list[PackageValidationResult]
    api_results: list[APIVerificationResult]
    execution_result: ExecutionResult | None
    repaired_code: str | None
    repair_prompt: str | None
    repaired_analysis: AnalysisResult | None
    repaired_package_results: list[PackageValidationResult]
    repaired_api_results: list[APIVerificationResult]
    repaired_execution_result: ExecutionResult | None
    model_name: str
    generation_config: dict[str, Any]
    repair_method: str | None
    latency_seconds: float


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
