"""Local-only staged native probe and smoke, using the established M7 evaluator."""
import argparse
import json
from pathlib import Path

from depguard.agent.probe import run_probe
from depguard.agent.tools import default_registry
from depguard.schemas import to_jsonable
from evaluation.interview_benchmark import evaluate_case, make_model, save, verify_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["probe", "smoke"])
    parser.add_argument("--config", default="configs/m7_qwen3_30b.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--probe-artifact")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Stage evidence is immutable; use a new path")
    config = json.loads(Path(args.config).read_text())
    if config["provider"] != "ollama":
        raise ValueError("This validation is local-only")
    model = make_model(config)
    before = model.runtime_metadata()
    if args.stage == "probe":
        result = to_jsonable(run_probe(model, default_registry().specs,
                                       timeout_seconds=config["agent"]["probe_timeout"], use_cache=False))
    else:
        probe = json.loads(Path(args.probe_artifact).read_text())
        if probe["result"]["status"] != "passed" or probe["config"] != config:
            raise ValueError("A passed full probe with this config is required before smoke")
        case = next(c for c in verify_manifest(Path("data/interview_eval/manifest.json"))["cases"]
                    if c["id"] == "json_names")
        result = evaluate_case(case, "loop", config, model)
    save(output, {"stage": args.stage, "config": config, "runtime_before": before,
                  "runtime_after": model.runtime_metadata(), "result": result})
    print(json.dumps({"artifact": str(output), "status": result.get("status"),
                      "termination": result.get("termination_reason", result.get("reason"))}))


if __name__ == "__main__":
    main()
