"""Content-addressed policy versions, atomic state, and a hash-chained audit."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .policy import Policy, Strategy, parse_policy

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state.json"
AUDIT = ROOT / "audit" / "evolution.jsonl"
MANIFEST = ROOT / "audit" / "trusted-manifest.json"
VERSION_DIR = ROOT / "versions"
CANDIDATE_DIR = ROOT / "candidates"
RESULT_DIR = ROOT / "results"
ZERO_HASH = "0" * 64
TRUSTED = ("harness/policy.py", "harness/benchmark.py", "harness/evaluator.py", "harness/storage.py", "harness/engine.py", "harness/cli.py")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        _sync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def save_policy(policy: Policy, directory: Path) -> str:
    parse_policy(policy.as_dict())
    data = policy.canonical()
    sha = digest(data)
    path = directory / f"{sha}.json"
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("content-address collision or corruption")
    else:
        atomic_write(path, data)
    return sha


def read_policy(sha: str, directory: Path | None = None) -> Policy:
    directory = VERSION_DIR if directory is None else directory
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid content address")
    data = (directory / f"{sha}.json").read_bytes()
    if digest(data) != sha:
        raise ValueError("policy version digest mismatch")
    return parse_policy(data)


def load_state() -> dict[str, Any]:
    assert_pinned_manifest()
    obj = json.loads(STATE.read_text(encoding="utf-8"))
    if set(obj) != {"schema", "active", "iteration"} or obj["schema"] != 1:
        raise ValueError("invalid state")
    if type(obj["iteration"]) is not int or obj["iteration"] < 0:
        raise ValueError("invalid iteration")
    read_policy(obj["active"])
    return obj


def write_state(active: str, iteration: int) -> None:
    read_policy(active)
    atomic_write(STATE, json_bytes({"schema": 1, "active": active, "iteration": iteration}))


def audit_records() -> list[dict[str, Any]]:
    if not AUDIT.exists():
        return []
    records = []
    previous = ZERO_HASH
    for number, line in enumerate(AUDIT.read_bytes().splitlines(), 1):
        record = json.loads(line)
        hash_value = record.pop("hash")
        if record.get("previous_hash") != previous or digest(json_bytes(record)) != hash_value:
            raise ValueError(f"audit chain broken at line {number}")
        record["hash"] = hash_value
        previous = hash_value
        records.append(record)
    return records


def append_audit(event: dict[str, Any]) -> dict[str, Any]:
    records = audit_records()
    item = {**event, "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": records[-1]["hash"] if records else ZERO_HASH}
    item["hash"] = digest(json_bytes(item))
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("ab") as handle:
        handle.write(json_bytes(item))
        handle.flush()
        os.fsync(handle.fileno())
    return item


def trusted_manifest() -> dict[str, str]:
    result = {name: digest((ROOT / name).read_bytes()) for name in TRUSTED}
    shared = Path(os.environ.get("HW13_SHARED_PATH", str(ROOT.parent / "shared")))
    for name in ("task.md", "evals/spec.md"):
        path = shared / name
        if path.is_file():
            result[f"shared/{name}"] = digest(path.read_bytes())
    return result


def assert_trusted(expected: dict[str, str]) -> None:
    if trusted_manifest() != expected:
        raise ValueError("trusted source or shared specification changed during evolution")


def assert_pinned_manifest() -> None:
    if not MANIFEST.is_file():
        raise ValueError("trusted manifest is missing")
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert_trusted(expected)


@contextmanager
def exclusive_lock() -> Iterator[None]:
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / ".harness.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def initialize() -> dict[str, Any]:
    if STATE.exists():
        return load_state()
    if MANIFEST.exists() or AUDIT.exists():
        raise ValueError("partial prior run detected; refusing to reinitialize")
    atomic_write(MANIFEST, json_bytes(trusted_manifest()))
    baseline = Policy((Strategy("input", "first"),))
    sha = save_policy(baseline, VERSION_DIR)
    write_state(sha, 0)
    append_audit({"event": "initialize", "iteration": 0, "baseline_score": None,
                  "candidate_score": None, "decision": "initialized",
                  "reason": "created immutable baseline policy", "policy_hash": sha})
    return load_state()


def recover_pending() -> None:
    records = audit_records()
    if not records or records[-1].get("event") != "commit_intent":
        return
    pending = records[-1]
    state = load_state()
    committed = state["active"] == pending["candidate_hash"]
    append_audit({"event": "recovery", "iteration": pending["iteration"],
                  "baseline_score": pending["baseline_score"],
                  "candidate_score": pending["candidate_score"],
                  "decision": "accepted" if committed else "rejected",
                  "reason": "recovered committed state" if committed else "rolled back interrupted commit",
                  "candidate_hash": pending["candidate_hash"]})


def commit(policy: Policy, iteration: int, baseline_score: int, candidate_score: int,
           fail_after_intent: bool = False) -> str:
    old = load_state()
    sha = save_policy(policy, VERSION_DIR)
    append_audit({"event": "commit_intent", "iteration": iteration,
                  "baseline_score": baseline_score, "candidate_score": candidate_score,
                  "decision": "pending", "reason": "candidate passed validation gate",
                  "baseline_hash": old["active"], "candidate_hash": sha})
    if fail_after_intent:
        raise RuntimeError("injected commit failure")
    write_state(sha, iteration)
    append_audit({"event": "commit", "iteration": iteration,
                  "baseline_score": baseline_score, "candidate_score": candidate_score,
                  "decision": "accepted", "reason": "atomic active pointer updated",
                  "baseline_hash": old["active"], "candidate_hash": sha})
    return sha
