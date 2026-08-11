from __future__ import annotations

from typing import Any


def format_chat_prompt(tokenizer: Any, prompt: str) -> str:
    """Apply the model's native instruction template to a repair/generation prompt."""
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt.strip()}],
        tokenize=False,
        add_generation_prompt=True,
    )
