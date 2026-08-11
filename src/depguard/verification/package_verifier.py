from __future__ import annotations

import importlib.metadata
import importlib.util
import sys

from depguard.schemas import ErrorCategory, ImportReference, PackageValidationResult


class PackageVerifier:
    """Deterministic package-level validation using the active Python environment."""

    def verify_imports(self, imports: list[ImportReference]) -> list[PackageValidationResult]:
        packages = sorted({ref.package for ref in imports if ref.level == 0 and ref.package})
        return [self.verify_package(package) for package in packages]

    def verify_package(self, package: str) -> PackageValidationResult:
        if not package:
            return PackageValidationResult(
                package=package,
                exists=False,
                status=ErrorCategory.HALLUCINATED_PACKAGE.value,
                reason="empty_package_name",
            )

        exists = self._package_exists(package)
        if not exists:
            return PackageValidationResult(
                package=package,
                exists=False,
                status=ErrorCategory.HALLUCINATED_PACKAGE.value,
                reason="not_importable_in_environment",
            )

        return PackageValidationResult(
            package=package,
            exists=True,
            status="valid",
            version=self._distribution_version(package),
        )

    @staticmethod
    def _package_exists(package: str) -> bool:
        if package in sys.builtin_module_names:
            return True
        stdlib_names = getattr(sys, "stdlib_module_names", set())
        if package in stdlib_names:
            return True
        try:
            return importlib.util.find_spec(package) is not None
        except (ImportError, AttributeError, ValueError):
            return False

    @staticmethod
    def _distribution_version(package: str) -> str | None:
        candidates = [package, package.replace("_", "-")]
        for candidate in candidates:
            try:
                return importlib.metadata.version(candidate)
            except importlib.metadata.PackageNotFoundError:
                continue
        return None
