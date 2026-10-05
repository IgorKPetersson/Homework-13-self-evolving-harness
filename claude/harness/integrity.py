"""Evaluator self-protection.

* MANIFEST.json pins the SHA-256 of every trusted harness file. Any edit to the
  judge, the benchmark or the accept rule makes the harness refuse to run
  until a human re-locks it (and the lock event is audited).
* The read-only shared challenge directory is fingerprinted at the start and
  end of each run; a change aborts the run.
"""
import hashlib
import json
from pathlib import Path

HARNESS_DIR = Path(__file__).parent
MANIFEST = HARNESS_DIR / "MANIFEST.json"
SHARED_DIR = Path("/workspace/shared")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harness_hashes():
    return {p.name: _sha(p) for p in sorted(HARNESS_DIR.glob("*.py"))}


def lock():
    MANIFEST.write_text(json.dumps(harness_hashes(), indent=2, sort_keys=True) + "\n")


def check_harness():
    """Return (ok, message)."""
    if not MANIFEST.exists():
        return False, "MANIFEST.json missing - run `python -m harness lock`"
    pinned, actual = json.loads(MANIFEST.read_text()), harness_hashes()
    changed = sorted(set(pinned) ^ set(actual) |
                     {k for k in pinned.keys() & actual.keys() if pinned[k] != actual[k]})
    return (not changed), ("harness files match manifest" if not changed
                           else f"harness files modified: {changed}")


def manifest_digest():
    return hashlib.sha256(MANIFEST.read_bytes()).hexdigest() if MANIFEST.exists() else None


def shared_fingerprint():
    if not SHARED_DIR.exists():
        return None
    h = hashlib.sha256()
    for p in sorted(SHARED_DIR.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(SHARED_DIR)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()
