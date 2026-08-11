from __future__ import annotations

import difflib
import importlib
import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from depguard.schemas import APIReference, APIVerificationResult, ErrorCategory
from depguard.verification.package_verifier import PackageVerifier

COMMON_REPLACEMENTS = {
    "read_smart_csv": "read_csv",
    "read_super_csv": "read_csv",
    "read_super_excel": "read_excel",
    "square_root": "sqrt",
}


@dataclass(frozen=True)
class _ModuleResolution:
    module: ModuleType | None
    module_path: str | None
    attr_parts: tuple[str, ...]
    import_error: str | None = None


class APIVerifier:
    """Validate API references with importlib, reflection, and conservative signatures."""

    def __init__(self, package_verifier: PackageVerifier | None = None) -> None:
        self.package_verifier = package_verifier or PackageVerifier()

    def verify_many(self, references: list[APIReference]) -> list[APIVerificationResult]:
        return [self.verify(reference) for reference in references]

    def verify(self, reference: APIReference) -> APIVerificationResult:
        package_result = self.package_verifier.verify_package(reference.package)
        if not package_result.exists:
            return APIVerificationResult(
                reference=reference,
                package_valid=False,
                module_valid=False,
                api_valid=False,
                status=ErrorCategory.HALLUCINATED_PACKAGE.value,
                reason=package_result.reason,
            )

        resolution = self._resolve_importable_prefix(reference.canonical_path)
        if not resolution.module:
            return APIVerificationResult(
                reference=reference,
                package_valid=True,
                module_valid=False,
                api_valid=False,
                status=ErrorCategory.HALLUCINATED_MODULE.value,
                reason=resolution.import_error or "module_not_importable",
            )

        obj = resolution.module
        prefix = resolution.module_path or reference.package
        attr_parts = list(resolution.attr_parts)
        for index, attr in enumerate(attr_parts):
            if not self._has_attribute(obj, attr):
                remaining = attr_parts[index:]
                category = self._missing_category(reference, remaining)
                suggestions = self._suggest(obj, attr, prefix)
                return APIVerificationResult(
                    reference=reference,
                    package_valid=True,
                    module_valid=category != ErrorCategory.HALLUCINATED_MODULE,
                    api_valid=False,
                    status=category.value,
                    reason=f"attribute_not_found:{attr}",
                    resolved_module=resolution.module_path,
                    suggestions=tuple(suggestions),
                )
            obj = getattr(obj, attr)
            prefix = f"{prefix}.{attr}"

        signature_error = self._signature_error(obj, reference)
        if signature_error:
            return APIVerificationResult(
                reference=reference,
                package_valid=True,
                module_valid=True,
                api_valid=False,
                status=ErrorCategory.INCORRECT_ARGUMENTS.value,
                reason=signature_error,
                resolved_module=resolution.module_path,
            )

        return APIVerificationResult(
            reference=reference,
            package_valid=True,
            module_valid=True,
            api_valid=True,
            status="valid",
            resolved_module=resolution.module_path,
        )

    def _resolve_importable_prefix(self, canonical_path: str) -> _ModuleResolution:
        parts = canonical_path.split(".")
        import_errors: list[str] = []
        for end in range(len(parts), 0, -1):
            module_path = ".".join(parts[:end])
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as exc:
                import_errors.append(str(exc))
                continue
            except (
                AttributeError,
                ImportError,
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                return _ModuleResolution(
                    module=None,
                    module_path=module_path,
                    attr_parts=tuple(parts[end:]),
                    import_error=f"{type(exc).__name__}: {exc}",
                )
            return _ModuleResolution(
                module=module,
                module_path=module_path,
                attr_parts=tuple(parts[end:]),
            )
        return _ModuleResolution(
            module=None,
            module_path=None,
            attr_parts=tuple(parts),
            import_error="no_importable_prefix",
        )

    @staticmethod
    def _has_attribute(obj: Any, attr: str) -> bool:
        try:
            inspect.getattr_static(obj, attr)
            return True
        except AttributeError:
            pass
        try:
            getattr(obj, attr)
            return True
        except AttributeError:
            return False
        except (ImportError, OSError, RuntimeError, TypeError, ValueError):
            return True

    @staticmethod
    def _missing_category(reference: APIReference, remaining_parts: list[str]) -> ErrorCategory:
        missing = remaining_parts[0] if remaining_parts else reference.object_path
        if len(remaining_parts) > 1 and missing[:1].islower():
            return ErrorCategory.HALLUCINATED_MODULE
        if reference.call_type == "method_or_attribute":
            return ErrorCategory.HALLUCINATED_METHOD_OR_ATTRIBUTE
        if missing[:1].isupper():
            return ErrorCategory.HALLUCINATED_CLASS
        if reference.is_call or reference.call_type in {"function_or_attribute", "imported_callable"}:
            return ErrorCategory.HALLUCINATED_FUNCTION
        return ErrorCategory.HALLUCINATED_METHOD_OR_ATTRIBUTE

    @staticmethod
    def _suggest(parent_obj: Any, missing_attr: str, prefix: str) -> list[str]:
        try:
            names = [name for name in dir(parent_obj) if not name.startswith("_")]
        except (RuntimeError, TypeError, ValueError):
            return []

        preferred = COMMON_REPLACEMENTS.get(missing_attr)
        suggestions: list[str] = []
        if preferred and preferred in names:
            suggestions.append(f"{prefix}.{preferred}")

        for match in difflib.get_close_matches(missing_attr, names, n=5, cutoff=0.45):
            candidate = f"{prefix}.{match}"
            if candidate not in suggestions:
                suggestions.append(candidate)
        return suggestions[:5]

    @staticmethod
    def _signature_error(obj: Any, reference: APIReference) -> str | None:
        if not reference.is_call or reference.arg_count is None:
            return None
        try:
            signature = inspect.signature(obj)
        except (TypeError, ValueError):
            return None

        params = list(signature.parameters.values())
        if reference.call_type == "method_or_attribute" and params and params[0].name in {"self", "cls"}:
            params = params[1:]

        has_varargs = any(param.kind == param.VAR_POSITIONAL for param in params)
        has_varkw = any(param.kind == param.VAR_KEYWORD for param in params)

        positional_params = [
            param
            for param in params
            if param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD}
        ]
        required_positional = [
            param for param in positional_params if param.default is inspect.Parameter.empty
        ]

        if reference.arg_count < len(required_positional):
            return "missing_required_positional_argument"
        if not has_varargs and reference.arg_count > len(positional_params):
            return "too_many_positional_arguments"

        if not has_varkw:
            accepted_keywords = {
                param.name
                for param in params
                if param.kind in {param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY}
            }
            unexpected = [name for name in reference.keyword_names if name not in accepted_keywords]
            if unexpected:
                return f"unexpected_keyword_argument:{unexpected[0]}"
        return None
