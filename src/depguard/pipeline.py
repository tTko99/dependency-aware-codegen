from __future__ import annotations

import time
from typing import Any

from depguard.analysis import DependencyAnalyzer
from depguard.execution import SandboxedExecutor
from depguard.models.base import CodeGenerator, CodeRepairModel
from depguard.repair.prompts import build_repair_prompt, strip_code_fence
from depguard.schemas import (
    APIReference,
    APIVerificationResult,
    ExecutionResult,
    PackageValidationResult,
    PipelineResult,
    RepairContext,
)
from depguard.verification import APIVerifier, PackageVerifier


class DependencyGuardPipeline:
    def __init__(
        self,
        *,
        generator: CodeGenerator | None = None,
        repair_model: CodeRepairModel | None = None,
        analyzer: DependencyAnalyzer | None = None,
        package_verifier: PackageVerifier | None = None,
        api_verifier: APIVerifier | None = None,
        executor: SandboxedExecutor | None = None,
        enable_api_validation: bool = True,
        enable_execution: bool = True,
        repair_method: str | None = "generic",
        repair_on_execution_error: bool = True,
    ) -> None:
        self.generator = generator
        self.repair_model = repair_model
        self.analyzer = analyzer or DependencyAnalyzer()
        self.package_verifier = package_verifier or PackageVerifier()
        self.api_verifier = api_verifier or APIVerifier(self.package_verifier)
        self.executor = executor or SandboxedExecutor()
        self.enable_api_validation = enable_api_validation
        self.enable_execution = enable_execution
        self.repair_method = repair_method
        self.repair_on_execution_error = repair_on_execution_error

    def run(
        self,
        *,
        requirement: str,
        code: str | None = None,
        test_code: str | None = None,
    ) -> PipelineResult:
        started = time.perf_counter()
        generated_code = code if code is not None else self._generate(requirement)

        analysis = self.analyzer.analyze(generated_code)
        package_results = self.package_verifier.verify_imports(analysis.imports)
        api_results = (
            self.api_verifier.verify_many(analysis.api_references)
            if self.enable_api_validation and not analysis.syntax_error
            else []
        )
        execution_result = (
            self.executor.execute(generated_code, test_code=test_code)
            if self.enable_execution
            else None
        )

        repaired_code: str | None = None
        repair_prompt: str | None = None
        repaired_analysis = None
        repaired_package_results: list[PackageValidationResult] = []
        repaired_api_results: list[APIVerificationResult] = []
        repaired_execution_result: ExecutionResult | None = None

        if self._should_repair(package_results, api_results, execution_result):
            context = self._build_repair_context(
                requirement=requirement,
                original_code=generated_code,
                package_results=package_results,
                api_results=api_results,
                execution_result=execution_result,
            )
            repair_prompt = build_repair_prompt(context)
            if self.repair_model is not None and self.repair_method:
                repaired_code = strip_code_fence(self.repair_model.repair(context))
                repaired_analysis = self.analyzer.analyze(repaired_code)
                repaired_package_results = self.package_verifier.verify_imports(
                    repaired_analysis.imports
                )
                repaired_api_results = (
                    self.api_verifier.verify_many(repaired_analysis.api_references)
                    if self.enable_api_validation and not repaired_analysis.syntax_error
                    else []
                )
                repaired_execution_result = (
                    self.executor.execute(repaired_code, test_code=test_code)
                    if self.enable_execution
                    else None
                )

        return PipelineResult(
            requirement=requirement,
            generated_code=generated_code,
            analysis=analysis,
            package_results=package_results,
            api_results=api_results,
            execution_result=execution_result,
            repaired_code=repaired_code,
            repair_prompt=repair_prompt,
            repaired_analysis=repaired_analysis,
            repaired_package_results=repaired_package_results,
            repaired_api_results=repaired_api_results,
            repaired_execution_result=repaired_execution_result,
            model_name=self._model_name(code_was_provided=code is not None),
            generation_config=self._generation_config(),
            repair_method=self.repair_method if self.repair_model else None,
            latency_seconds=time.perf_counter() - started,
        )

    def _generate(self, requirement: str) -> str:
        if self.generator is None:
            raise ValueError("A generator is required when no code is supplied.")
        return self.generator.generate(requirement)

    def _model_name(self, *, code_was_provided: bool) -> str:
        if code_was_provided:
            return "provided-code"
        return getattr(self.generator, "model_name", "unknown-generator")

    def _generation_config(self) -> dict[str, Any]:
        return dict(getattr(self.generator, "generation_config", {}))

    def _should_repair(
        self,
        package_results: list[PackageValidationResult],
        api_results: list[APIVerificationResult],
        execution_result: ExecutionResult | None,
    ) -> bool:
        if any(not result.exists for result in package_results):
            return True
        if any(not result.api_valid for result in api_results):
            return True
        return bool(
            self.repair_on_execution_error
            and execution_result
            and execution_result.status != "passed"
        )

    def _build_repair_context(
        self,
        *,
        requirement: str,
        original_code: str,
        package_results: list[PackageValidationResult],
        api_results: list[APIVerificationResult],
        execution_result: ExecutionResult | None,
    ) -> RepairContext:
        suspicious = self._select_suspicious_reference(api_results)
        candidates: tuple[str, ...] = ()
        if suspicious:
            for result in api_results:
                if result.reference == suspicious:
                    candidates = result.suggestions
                    break
        return RepairContext(
            requirement=requirement,
            original_code=original_code,
            package_results=package_results,
            api_results=api_results,
            execution_result=execution_result,
            suspicious_reference=suspicious,
            candidate_apis=candidates,
            repair_method=self.repair_method or "none",
        )

    @staticmethod
    def _select_suspicious_reference(
        api_results: list[APIVerificationResult],
    ) -> APIReference | None:
        for result in api_results:
            if not result.api_valid:
                return result.reference
        return None
