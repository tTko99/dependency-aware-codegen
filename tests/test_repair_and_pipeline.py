from depguard.execution import SandboxedExecutor
from depguard.models.smoke import HeuristicRepairModel
from depguard.pipeline import DependencyGuardPipeline


def test_repair_prompt_contains_structured_evidence() -> None:
    pipeline = DependencyGuardPipeline(
        repair_model=HeuristicRepairModel(),
        executor=SandboxedExecutor(timeout_seconds=1),
        repair_method="heuristic",
    )
    result = pipeline.run(
        requirement="Compute the square root of four.",
        code="import math\nprint(math.square_root(4))\n",
    )

    assert result.repair_prompt is not None
    assert "Requirement:" in result.repair_prompt
    assert "math.square_root" in result.repair_prompt
    assert "Candidate APIs:" in result.repair_prompt


def test_end_to_end_heuristic_repair_smoke() -> None:
    pipeline = DependencyGuardPipeline(
        repair_model=HeuristicRepairModel(),
        executor=SandboxedExecutor(timeout_seconds=1),
        repair_method="heuristic",
    )
    result = pipeline.run(
        requirement="Compute the square root of four.",
        code="import math\nprint(math.square_root(4))\n",
    )

    assert result.execution_result is not None
    assert result.execution_result.status == "failed"
    assert result.repaired_code is not None
    assert "math.sqrt" in result.repaired_code
    assert result.repaired_execution_result is not None
    assert result.repaired_execution_result.status == "passed"


def test_prompt_builder_is_code_only_instruction() -> None:
    pipeline = DependencyGuardPipeline(
        repair_model=HeuristicRepairModel(),
        executor=SandboxedExecutor(timeout_seconds=1),
        repair_method="heuristic",
    )
    result = pipeline.run(requirement="Compute sqrt.", code="import math\nmath.square_root(4)\n")
    context_prompt = result.repair_prompt or ""

    assert "complete corrected program only" in context_prompt
