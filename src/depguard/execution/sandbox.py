from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from depguard.errors import classify_execution_error, extract_error_type
from depguard.schemas import ErrorCategory, ExecutionResult


class SandboxedExecutor:
    """Run generated Python code in a subprocess with timeout and temp directory isolation."""

    def __init__(
        self,
        timeout_seconds: float = 5.0,
        memory_limit_mb: int | None = None,
        python_executable: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.python_executable = python_executable or sys.executable

    def execute(self, code: str, test_code: str | None = None) -> ExecutionResult:
        with tempfile.TemporaryDirectory(prefix="depguard_exec_") as tmp:
            workdir = Path(tmp)
            if test_code:
                (workdir / "solution.py").write_text(code, encoding="utf-8")
                (workdir / "test_solution.py").write_text(test_code, encoding="utf-8")
                command = [self.python_executable, "-I", "-m", "pytest", "-q", str(workdir)]
            else:
                script_path = workdir / "candidate.py"
                script_path.write_text(code, encoding="utf-8")
                command = [self.python_executable, "-I", str(script_path)]
            return self._run(command, workdir)

    def _run(self, command: list[str], workdir: Path) -> ExecutionResult:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "TEMP": str(workdir),
            "TMP": str(workdir),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                preexec_fn=self._resource_limiter() if os.name == "posix" else None,
                check=False,
            )
            elapsed = time.perf_counter() - started
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started
            return ExecutionResult(
                status="timeout",
                return_code=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                error_type="TimeoutExpired",
                error_category=ErrorCategory.TIMEOUT.value,
                execution_time=elapsed,
                timed_out=True,
            )

        if completed.returncode == 0:
            category = ErrorCategory.UNKNOWN.value
            status = "passed"
            error_type = None
        else:
            diagnostic_output = "\n".join(
                output for output in (completed.stderr, completed.stdout) if output
            )
            error_category = classify_execution_error(
                diagnostic_output,
                return_code=completed.returncode,
            )
            category = error_category.value
            status = "failed"
            error_type = extract_error_type(diagnostic_output)

        return ExecutionResult(
            status=status,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error_type=error_type,
            error_category=category,
            execution_time=elapsed,
            timed_out=False,
        )

    def _resource_limiter(self):
        if not self.memory_limit_mb:
            return None

        def limit_resources() -> None:
            import resource

            memory_bytes = self.memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

        return limit_resources
