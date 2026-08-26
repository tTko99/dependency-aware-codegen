from __future__ import annotations

from typing import Any

from depguard.config import load_config
from depguard.models.ollama import OllamaRepairModel
from evaluation import run_benchmark


def test_evaluation_config_builds_64_token_ollama_pipeline_without_generator() -> None:
    config = load_config("configs/evaluation_7b_ollama.yaml")

    pipeline = run_benchmark.build_pipeline(config, "api_aware_generic")

    assert pipeline.generator is None
    assert isinstance(pipeline.repair_model, OllamaRepairModel)
    assert pipeline.repair_model.model_name == "qwen2.5-coder:7b"
    assert pipeline.repair_model.generation_config["max_new_tokens"] == 64
    assert pipeline.repair_model.generation_config["context_length"] == 4096
    assert pipeline.enable_api_validation is True
    assert pipeline.repair_method == "ollama"
    assert pipeline.repair_on_execution_error is False


def test_historical_evaluation_config_still_selects_hf_backend(monkeypatch) -> None:
    class FakeHFRepairModel:
        def __init__(self, **kwargs: Any) -> None:
            self.model_name = kwargs["model_name"]
            self.generation_config = kwargs

    monkeypatch.setattr(run_benchmark, "HFCausalRepairModel", FakeHFRepairModel)
    config = load_config("configs/evaluation_expanded_selected.yaml")

    pipeline = run_benchmark.build_pipeline(config, "api_aware_generic")

    assert pipeline.generator is None
    assert isinstance(pipeline.repair_model, FakeHFRepairModel)
    assert pipeline.repair_model.model_name == "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    assert pipeline.repair_method == "generic"
