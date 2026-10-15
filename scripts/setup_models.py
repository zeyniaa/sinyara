"""Explicit, reproducible model preparation; never downloads on import."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--whisper", action="store_true")
parser.add_argument("--aasist", action="store_true")
parser.add_argument("--revision", help="Pinned clovaai/aasist commit; default resolves official HEAD and records it")
args = parser.parse_args()

if args.whisper:
    from faster_whisper import WhisperModel
    WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    print("Whisper small multilingual: ready (CPU INT8).")

if args.aasist:
    revision = args.revision
    if not revision:
        request = Request("https://api.github.com/repos/clovaai/aasist/commits/main", headers={"User-Agent": "Sinyara-model-setup"})
        with urlopen(request, timeout=30) as response:
            revision = json.load(response)["sha"]
    if len(revision) != 40 or not all(c in "0123456789abcdef" for c in revision):
        raise ValueError("Use a full official Git commit SHA")
    root = Path(".cache/aasist")
    hashes = {}
    for name in ["models/AASIST.py", "models/weights/AASIST.pth", "config/AASIST.conf", "LICENSE"]:
        with urlopen(f"https://raw.githubusercontent.com/clovaai/aasist/{revision}/{name}", timeout=90) as response:
            data = response.read()
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (root / "provenance.json").write_text(json.dumps({"repository": "https://github.com/clovaai/aasist", "revision": revision, "sha256": hashes}, indent=2))
    print(json.dumps({"aasist": "ready", "revision": revision, "directory": str(root)}))
