from __future__ import annotations

from pathlib import Path
from typing import Any


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    suffix = config_path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        import yaml

        with config_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    if suffix == ".json":
        import json

        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    raise ValueError(f"Unsupported config format: {config_path.suffix}")
