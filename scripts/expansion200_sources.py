"""Archive an exact public HumanEvalPack revision without loading dataset scripts."""

import json
import urllib.request
from pathlib import Path

from evaluation.agent_benchmark import sha
from evaluation.interview_benchmark import now, save
from scripts.horizontal_sources import immutable

ROOT = Path("data/expansion200_v1/upstream/humanevalpack")
REVISION = "9a41762f73a8cb23bb5811b73d5aab164efcf378"


def main():
    inventory = {}
    for name in ["README.md", "python/test-00000-of-00001.parquet"]:
        url = f"https://huggingface.co/datasets/bigcode/humanevalpack/resolve/{REVISION}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        dest = ROOT / name
        immutable(dest, content)
        inventory[name] = {"url": url, "sha256": sha(content), "bytes": len(content)}
    save(
        ROOT / "inventory.json",
        {
            "revision": REVISION,
            "fetched_at": now(),
            "files": inventory,
            "source_kind": "public_authored_bug_benchmark",
            "production_defects": False,
            "description": "Human-written bugs in HumanEval solutions; not naturally occurring production bugs.",
        },
    )
    import pyarrow.parquet as pq

    rows = pq.read_table(ROOT / "python/test-00000-of-00001.parquet").to_pylist()
    immutable(ROOT / "python_records.json", json.dumps(rows, ensure_ascii=False, indent=2).encode())
    print("Archived", len(rows), "public benchmark records; keys:", list(rows[0]))


if __name__ == "__main__":
    main()
