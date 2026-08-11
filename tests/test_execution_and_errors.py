from depguard.errors import classify_execution_error
from depguard.execution import SandboxedExecutor
from depguard.schemas import ErrorCategory


def test_error_classifier_maps_tracebacks() -> None:
    stderr = "Traceback (most recent call last):\n  File \"x\", line 1\nAttributeError: nope"

    assert classify_execution_error(stderr, return_code=1) == ErrorCategory.ATTRIBUTE_ERROR


def test_executor_captures_success_and_failure() -> None:
    executor = SandboxedExecutor(timeout_seconds=1)

    passed = executor.execute("print('ok')\n")
    failed = executor.execute("raise ValueError('bad')\n")

    assert passed.status == "passed"
    assert passed.stdout.strip() == "ok"
    assert failed.status == "failed"
    assert failed.error_category == "value_error"


def test_executor_timeout() -> None:
    executor = SandboxedExecutor(timeout_seconds=0.2)

    result = executor.execute("import time\ntime.sleep(2)\n")

    assert result.status == "timeout"
    assert result.timed_out is True
    assert result.error_category == "timeout"


def test_executor_runs_isolated_pytest_unit_tests() -> None:
    result = SandboxedExecutor(timeout_seconds=2).execute(
        "def add(left, right):\n    return left + right\n",
        test_code=(
            "from solution import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    )

    assert result.status == "passed"


def test_executor_classifies_pytest_collection_error_from_stdout() -> None:
    result = SandboxedExecutor(timeout_seconds=2).execute(
        "result = len()\n",
        test_code="from solution import result\n",
    )

    assert result.status == "failed"
    assert result.error_type == "TypeError"
    assert result.error_category == "incorrect_arguments"
