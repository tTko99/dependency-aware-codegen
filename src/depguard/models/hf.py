from __future__ import annotations

from typing import Any

from depguard.models.chat import format_chat_prompt
from depguard.repair.prompts import build_repair_prompt, strip_code_fence
from depguard.schemas import RepairContext


class HFCausalCodeGenerator:
    """Hugging Face causal LM inference with native instruction chat templates."""

    def __init__(
        self,
        model_name: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        top_p: float = 1.0,
        repetition_penalty: float = 1.0,
        seed: int | None = 42,
        device_map: str | None = "auto",
        torch_dtype: str = "auto",
        trust_remote_code: bool = False,
        adapter_path: str | None = None,
        local_files_only: bool = False,
        use_chat_template: bool = True,
    ) -> None:
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

        if seed is not None:
            set_seed(seed)

        self.model_name = model_name
        self.use_chat_template = use_chat_template
        self.generation_config: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "seed": seed,
            "device_map": device_map,
            "torch_dtype": torch_dtype,
            "adapter_path": adapter_path,
            "use_chat_template": use_chat_template,
        }
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=trust_remote_code,
            local_files_only=local_files_only,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        model_kwargs: dict[str, Any] = {
            "device_map": device_map,
            "trust_remote_code": trust_remote_code,
            "local_files_only": local_files_only,
            "low_cpu_mem_usage": True,
        }
        dtype = _resolve_dtype(torch, torch_dtype)
        if dtype != "auto":
            dtype_key = "dtype" if int(transformers.__version__.split(".", maxsplit=1)[0]) >= 5 else "torch_dtype"
            model_kwargs[dtype_key] = dtype
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        if adapter_path:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(self.model, adapter_path)
        self.model.eval()

    def generate(self, requirement: str) -> str:
        prompt = (
            "Write a Python solution for the following requirement. "
            "Return Python code only.\n\n"
            f"Requirement:\n{requirement.strip()}\n"
        )
        return self.generate_from_prompt(prompt)

    def generate_from_prompt(self, prompt: str) -> str:
        model_prompt = format_chat_prompt(self.tokenizer, prompt) if self.use_chat_template else prompt
        inputs = self.tokenizer(model_prompt, return_tensors="pt", add_special_tokens=False)
        device = next(self.model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        temperature = float(self.generation_config["temperature"])
        do_sample = temperature > 0
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": int(self.generation_config["max_new_tokens"]),
            "do_sample": do_sample,
            "repetition_penalty": float(self.generation_config["repetition_penalty"]),
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if do_sample:
            generation_kwargs["temperature"] = temperature
            generation_kwargs["top_p"] = float(self.generation_config["top_p"])

        with self._torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generation_kwargs)
        prompt_tokens = inputs["input_ids"].shape[-1]
        new_tokens = output_ids[0][prompt_tokens:]
        decoded = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        return strip_code_fence(decoded)


class HFCausalRepairModel(HFCausalCodeGenerator):
    """Repair model using a base causal LM and an optional PEFT adapter."""

    def repair(self, context: RepairContext) -> str:
        return self.generate_from_prompt(build_repair_prompt(context))


def _resolve_dtype(torch_module: Any, value: str) -> Any:
    if value == "auto":
        return "auto"
    try:
        return getattr(torch_module, value)
    except AttributeError as exc:
        raise ValueError(f"Unsupported torch dtype: {value}") from exc
