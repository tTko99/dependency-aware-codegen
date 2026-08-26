from __future__ import annotations

import json
from argparse import Namespace
from io import BytesIO
from typing import Any, Self
from urllib.error import HTTPError, URLError

import pytest

from depguard import cli
from depguard.config import load_config
from depguard.models.ollama import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaRepairModel,
    OllamaResponseError,
)
from depguard.schemas import RepairContext


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def repair_context() -> RepairContext:
    return RepairContext(
        requirement="Compute a square root.",
        original_code="import math\nresult = math.square_root(4)\n",
        package_results=[],
        api_results=[],
        execution_result=None,
        suspicious_reference=None,
        candidate_apis=("math.sqrt",),
        repair_method="ollama",
    )


def test_ollama_repair_constructs_chat_request_and_extracts_code(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request, *, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHTTPResponse(
            {
                "message": {"role": "assistant", "content": "```python\nprint('fixed')\n```"},
                "total_duration": 123,
                "eval_count": 7,
                "done_reason": "stop",
            }
        )

    monkeypatch.setattr("depguard.models.ollama.urlopen", fake_urlopen)
    model = OllamaRepairModel(
        "qwen2.5-coder:7b",
        base_url="http://localhost:11434/",
        timeout_seconds=12,
        max_new_tokens=96,
        context_length=4096,
    )

    repaired = model.repair(repair_context())

    assert repaired == "print('fixed')"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "qwen2.5-coder:7b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["num_predict"] == 96
    assert captured["payload"]["options"]["num_ctx"] == 4096
    assert "Candidate APIs: math.sqrt" in captured["payload"]["messages"][0]["content"]
    assert model.last_response_metadata == {
        "total_duration": 123,
        "eval_count": 7,
        "done_reason": "stop",
    }


def test_ollama_runtime_metadata_reports_exact_model_and_gpu_placement(monkeypatch) -> None:
    responses = {
        "/api/version": {"version": "0.32.5"},
        "/api/tags": {
            "models": [
                {
                    "name": "qwen2.5-coder:7b",
                    "digest": "exact-digest",
                    "details": {
                        "parameter_size": "7.6B",
                        "quantization_level": "Q4_K_M",
                    },
                }
            ]
        },
        "/api/ps": {
            "models": [
                {
                    "name": "qwen2.5-coder:7b",
                    "size": 100,
                    "size_vram": 100,
                    "context_length": 4096,
                }
            ]
        },
    }

    def fake_urlopen(request, *, timeout):
        path = request.full_url.removeprefix("http://127.0.0.1:11434")
        return FakeHTTPResponse(responses[path])

    monkeypatch.setattr("depguard.models.ollama.urlopen", fake_urlopen)
    metadata = OllamaRepairModel("qwen2.5-coder:7b").runtime_metadata()

    assert metadata["ollama_version"] == "0.32.5"
    assert metadata["installed_model"]["digest"] == "exact-digest"
    assert metadata["runtime"]["processor_placement"] == "gpu"


def test_ollama_connection_error_is_actionable(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("depguard.models.ollama.urlopen", unavailable)

    with pytest.raises(OllamaConnectionError, match="http://127.0.0.1:11434"):
        OllamaRepairModel("qwen2.5-coder:7b").repair(repair_context())


def test_ollama_missing_model_error_names_configured_tag(monkeypatch) -> None:
    def missing(request, *, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            hdrs=None,
            fp=BytesIO(b'{"error":"model not found"}'),
        )

    monkeypatch.setattr("depguard.models.ollama.urlopen", missing)

    with pytest.raises(OllamaModelNotFoundError, match="missing:7b"):
        OllamaRepairModel("missing:7b").repair(repair_context())


def test_ollama_empty_repair_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "depguard.models.ollama.urlopen",
        lambda request, timeout: FakeHTTPResponse({"message": {"content": ""}}),
    )

    with pytest.raises(OllamaResponseError, match="no repair text"):
        OllamaRepairModel("qwen2.5-coder:7b").repair(repair_context())


def test_engineering_config_selects_only_ollama_repair_model() -> None:
    config = load_config("configs/engineering_7b_ollama.yaml")
    args = Namespace(
        code=None,
        code_file="external.py",
        generator=None,
        repair=None,
        timeout=None,
    )

    pipeline = cli._build_pipeline(config, args)

    assert pipeline.generator is None
    assert isinstance(pipeline.repair_model, OllamaRepairModel)
    assert pipeline.repair_model.model_name == "qwen2.5-coder:7b"
    assert pipeline.repair_method == "ollama"


def test_historical_hf_repair_selection_remains_available(monkeypatch) -> None:
    class FakeHFRepairModel:
        def __init__(self, **kwargs: Any) -> None:
            self.model_name = kwargs["model_name"]
            self.generation_config = kwargs

    monkeypatch.setattr(cli, "HFCausalRepairModel", FakeHFRepairModel)
    args = Namespace(
        code="print('supplied')",
        code_file=None,
        generator=None,
        repair=None,
        timeout=None,
    )
    config = {
        "repair": {"kind": "hf", "hf": {"model_name": "historical-0.5b"}},
        "execution": {"enabled": False},
    }

    pipeline = cli._build_pipeline(config, args)

    assert pipeline.generator is None
    assert isinstance(pipeline.repair_model, FakeHFRepairModel)
    assert pipeline.repair_model.model_name == "historical-0.5b"
    assert pipeline.repair_method == "generic"
