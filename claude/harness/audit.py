"""Append-only, hash-chained audit log (JSON Lines).

Every entry stores the SHA-256 of the previous entry, so editing, deleting or
reordering any historic line is detected by `verify()`.
"""
import hashlib
import json
from datetime import datetime, timezone

GENESIS = "0" * 64


def _digest(entry):
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append(path, event, **fields):
    entries = read(path)
    entry = {"seq": len(entries) + 1,
             "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "event": event, **fields,
             "prev_hash": entries[-1]["entry_hash"] if entries else GENESIS}
    entry["entry_hash"] = _digest(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def verify(path):
    """Return (ok, message)."""
    prev = GENESIS
    for i, entry in enumerate(read(path), start=1):
        if entry.get("seq") != i:
            return False, f"entry {i}: sequence break"
        if entry.get("prev_hash") != prev:
            return False, f"entry {i}: chain broken (prev_hash mismatch)"
        if _digest(entry) != entry.get("entry_hash"):
            return False, f"entry {i}: content modified (hash mismatch)"
        prev = entry["entry_hash"]
    return True, "audit log intact"
