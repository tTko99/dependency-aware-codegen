"""Dependency-aware validation and repair for LLM-generated Python code."""

from depguard.pipeline import DependencyGuardPipeline
from depguard.schemas import (
    APIReference,
    APIVerificationResult,
    ExecutionResult,
    ImportReference,
    PackageValidationResult,
    PipelineResult,
)

__all__ = [
    "APIReference",
    "APIVerificationResult",
    "DependencyGuardPipeline",
    "ExecutionResult",
    "ImportReference",
    "PackageValidationResult",
    "PipelineResult",
]

__version__ = "0.1.0"
