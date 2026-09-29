"""Archive released public source without installing or executing it."""

import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path("data/horizontal_eval_v1/upstream")
VERSIONS = ("8.0.0", "8.1.0", "8.7.0", "8.8.0", "8.10.0", "8.11.0", "9.0.0", "9.1.0")


def fetch(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "dependency-aware-codegen-evaluation"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"Existing evidence differs: {path}")
    path.write_bytes(data)


def main():
    for version in VERSIONS:
        folder = ROOT / version
        if (folder / "inventory.json").exists():
            continue
        url = f"https://pypi.org/pypi/more-itertools/{version}/json"
        metadata = json.loads(fetch(url))
        entry = next(x for x in metadata["urls"] if x["packagetype"] == "sdist")
        archive = fetch(entry["url"])
        digest = hashlib.sha256(archive).hexdigest()
        if digest != entry["digests"]["sha256"]:
            raise ValueError("Release archive hash mismatch")
        inventory = {}
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            for member in bundle.getmembers():
                relative = Path(*Path(member.name).parts[1:])
                if not member.isfile() or not relative.parts or ".." in relative.parts:
                    continue
                if relative.suffix not in {".py", ".rst"} and relative.name not in {
                    "LICENSE",
                    "LICENSE.txt",
                }:
                    continue
                data = bundle.extractfile(member).read()
                name = relative.as_posix() + ".txt"
                immutable(folder / name, data)
                inventory[name] = hashlib.sha256(data).hexdigest()
        evidence = {
            "project": "more-itertools",
            "version": version,
            "metadata_url": url,
            "archive_url": entry["url"],
            "archive_sha256": digest,
            "files": inventory,
            "release_notes": "https://more-itertools.readthedocs.io/en/v10.5.0/versions.html",
        }
        immutable(folder / "inventory.json", (json.dumps(evidence, indent=2) + "\n").encode())
        print("Archived more-itertools " + version, flush=True)


if __name__ == "__main__":
    main()
