"""Ollama native single-tool-call decision protocol. Text alone is not an action."""

from depguard.agent.contracts import AgentDecision
from depguard.models.ollama import OllamaRepairModel
from depguard.models.tool_protocol import native_decision, provider_tools


class OllamaAgentModel(OllamaRepairModel):
    provider = "ollama"
    one_shot_supported = True

    def probe_identity(self):
        return {"provider": self.provider, "model": self.model_name,
                "endpoint": self.base_url, "generation": self.generation_config}

    def decide(self, messages, tools, *, timeout_seconds):
        self.timeout_seconds = timeout_seconds
        cfg = self.generation_config
        options = {"num_predict": cfg["max_new_tokens"], "temperature": cfg["temperature"],
                   "top_p": cfg["top_p"], "repeat_penalty": cfg["repetition_penalty"]}
        if cfg["seed"] is not None:
            options["seed"] = cfg["seed"]
        if cfg["context_length"] is not None:
            options["num_ctx"] = cfg["context_length"]
        try:
            return self._decide(messages, tools, options)
        except Exception as exc:  # noqa: BLE001 - structured provider boundary
            return AgentDecision(kind="provider_error", error_code=type(exc).__name__,
                                 message="Ollama request failed; check endpoint and model tag")

    def _decide(self, messages, tools, options):
        # role=tool + tool_name is Ollama's observation format. Keep call ids too:
        # current versions accept the association, and assistant ids must round-trip.
        response = self._post_json("/api/chat", {
            "model": self.model_name, "stream": False,
            "messages": messages, "options": options,
            "tools": provider_tools(tools),
            "keep_alive": self.generation_config["keep_alive"],
        })
        decision = native_decision(response.get("message"), string_arguments=True)
        if isinstance(decision.raw_response, dict):
            message = response.get("message", {})
            calls = message.get("tool_calls") or []
            if isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], dict):
                function = calls[0].get("function", {})
                if isinstance(function, dict):
                    args = function.get("arguments")
                    decision.raw_response["argument_type"] = (
                        "object" if isinstance(args, dict) else "string" if isinstance(args, str)
                        else type(args).__name__)
            usage = {k: response[k] for k in (
                "prompt_eval_count", "eval_count") if isinstance(response.get(k), int)}
            if usage:
                decision.raw_response["usage"] = usage
            if isinstance(response.get("model"), str):
                decision.raw_response["provider_model"] = response["model"]
        return decision
