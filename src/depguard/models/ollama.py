from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from depguard.repair.prompts import build_repair_prompt, strip_code_fence
from depguard.schemas import RepairContext


class OllamaError(RuntimeError):
    """Base error raised by the local Ollama repair backend."""


class OllamaConnectionError(OllamaError):
    """Raised when the configured Ollama API cannot be reached."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when Ollama does not have the configured model tag."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an unusable response."""


class OllamaRepairModel:
    """One-shot repair model backed by Ollama's local chat API."""

    def __init__(
        self,
        model_name: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 180.0,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        top_p: float = 1.0,
        repetition_penalty: float = 1.0,
        seed: int | None = 42,
        keep_alive: str | None = "5m",
        context_length: int | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("Ollama model_name must not be empty.")
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout_seconds must be positive.")
        if max_new_tokens <= 0:
            raise ValueError("Ollama max_new_tokens must be positive.")
        if context_length is not None and context_length <= 0:
            raise ValueError("Ollama context_length must be positive when provided.")

        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.generation_config: dict[str, Any] = {
            "backend": "ollama",
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "max_new_tokens": int(max_new_tokens),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "repetition_penalty": float(repetition_penalty),
            "seed": seed,
            "keep_alive": keep_alive,
            "context_length": context_length,
        }
        self.last_response_metadata: dict[str, Any] = {}

    def repair(self, context: RepairContext) -> str:
        options: dict[str, Any] = {
            "num_predict": self.generation_config["max_new_tokens"],
            "temperature": self.generation_config["temperature"],
            "top_p": self.generation_config["top_p"],
            "repeat_penalty": self.generation_config["repetition_penalty"],
        }
        if self.generation_config["seed"] is not None:
            options["seed"] = self.generation_config["seed"]
        if self.generation_config["context_length"] is not None:
            options["num_ctx"] = self.generation_config["context_length"]

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": build_repair_prompt(context)}],
            "stream": False,
            "options": options,
        }
        if self.generation_config["keep_alive"] is not None:
            payload["keep_alive"] = self.generation_config["keep_alive"]

        response = self._post_json("/api/chat", payload)
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseError(
                f"Ollama model {self.model_name!r} returned no repair text."
            )

        metadata_keys = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "done_reason",
        )
        self.last_response_metadata = {
            key: response[key] for key in metadata_keys if key in response
        }
        return strip_code_fence(content)

    def runtime_metadata(self) -> dict[str, Any]:
        """Return local model identity and current Ollama placement metadata."""
        version_response = self._get_json("/api/version")
        tags_response = self._get_json("/api/tags")
        running_response = self._get_json("/api/ps")

        installed = next(
            (
                model
                for model in tags_response.get("models", [])
                if isinstance(model, dict)
                and self.model_name in {model.get("name"), model.get("model")}
            ),
            None,
        )
        running = next(
            (
                model
                for model in running_response.get("models", [])
                if isinstance(model, dict)
                and self.model_name in {model.get("name"), model.get("model")}
            ),
            None,
        )

        runtime: dict[str, Any] | None = None
        if running is not None:
            size = running.get("size")
            size_vram = running.get("size_vram")
            placement = None
            if isinstance(size, int) and isinstance(size_vram, int) and size > 0:
                if size_vram == 0:
                    placement = "cpu"
                elif size_vram >= size:
                    placement = "gpu"
                else:
                    placement = "hybrid"
            runtime = {
                "size_bytes": size,
                "size_vram_bytes": size_vram,
                "context_length": running.get("context_length"),
                "expires_at": running.get("expires_at"),
                "processor_placement": placement,
            }

        return {
            "backend": "ollama",
            "endpoint": self.base_url,
            "ollama_version": version_response.get("version"),
            "configured_model_tag": self.model_name,
            "installed_model": installed,
            "runtime": runtime,
        }

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(path, payload)

    def _get_json(self, path: str) -> dict[str, Any]:
        return self._request_json(path)

    def _request_json(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = _http_error_detail(exc)
            if exc.code == 404 or "not found" in detail.lower():
                raise OllamaModelNotFoundError(
                    f"Ollama model {self.model_name!r} was not found at {self.base_url}. "
                    "Check the exact local tag with `ollama list`."
                ) from exc
            raise OllamaResponseError(
                f"Ollama API returned HTTP {exc.code} for {url}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaConnectionError(
                f"Could not reach the Ollama API at {self.base_url} within "
                f"{self.timeout_seconds:g} seconds: {exc}"
            ) from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"Ollama API at {url} returned invalid JSON."
            ) from exc
        if not isinstance(decoded, dict):
            raise OllamaResponseError(f"Ollama API at {url} returned a non-object response.")
        if decoded.get("error"):
            detail = str(decoded["error"])
            if "not found" in detail.lower():
                raise OllamaModelNotFoundError(
                    f"Ollama model {self.model_name!r} was not found at {self.base_url}: {detail}"
                )
            raise OllamaResponseError(f"Ollama API error for {self.model_name!r}: {detail}")
        return decoded


def _http_error_detail(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8")
        decoded = json.loads(body)
        if isinstance(decoded, dict) and decoded.get("error"):
            return str(decoded["error"])
        return body or str(error.reason)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return str(error.reason)
