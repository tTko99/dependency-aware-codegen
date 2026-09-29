"""Download a pinned public benchmark over HTTPS; no version-control operations."""
import argparse
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

REVISION = "4257f44b0ff1181dedaedee6a447e133219fcebf"
ROOT = Path("data/external_eval_v1/upstream")


def fetch():
    url = f"https://codeload.github.com/jkoppel/QuixBugs/zip/{REVISION}"
    request = urllib.request.Request(url, headers={"User-Agent": "depguard-evaluation"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive = response.read()
    inventory = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for info in bundle.infolist():
            relative = Path(*Path(info.filename).parts[1:])
            if info.is_dir() or not relative.parts or ".." in relative.parts:
                continue
            if relative.parts[0] not in {
                "python_programs", "correct_python_programs", "python_testcases",
                "json_testcases", "LICENSE", "README.md",
            }:
                continue
            # Upstream files are inert evidence, not importable local modules.
            target = ROOT / (relative.as_posix() + ".txt")
            data = bundle.read(info)
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f"Existing source differs: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            inventory[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    metadata = {"repository": "https://github.com/jkoppel/QuixBugs", "revision": REVISION,
                "archive_url": url, "archive_sha256": hashlib.sha256(archive).hexdigest(),
                "files": inventory}
    target = ROOT / "inventory.json"
    encoded = (json.dumps(metadata, indent=2) + "\n").encode()
    if target.exists() and target.read_bytes() != encoded:
        raise ValueError("Existing upstream inventory differs")
    target.write_bytes(encoded)
    print(f"Archived {len(inventory)} source files at {REVISION}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    fetch()
