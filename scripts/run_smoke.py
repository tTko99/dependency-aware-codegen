from __future__ import annotations

import json

from depguard.execution import SandboxedExecutor
from depguard.models.smoke import HeuristicRepairModel, HeuristicSmokeCodeGenerator
from depguard.pipeline import DependencyGuardPipeline
from depguard.schemas import to_jsonable


def main() -> int:
    pipeline = DependencyGuardPipeline(
        generator=HeuristicSmokeCodeGenerator(),
        repair_model=HeuristicRepairModel(),
        executor=SandboxedExecutor(timeout_seconds=2),
        repair_method="heuristic",
    )
    result = pipeline.run(requirement="Compute the square root of four.")
    print(json.dumps(to_jsonable(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
