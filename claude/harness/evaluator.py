"""The judge: static validation + sandboxed execution + scoring.

The same `evaluate_source` procedure is applied to the current version and to
every candidate. Scores are computed in this (trusted) process from raw
outputs; nothing the candidate prints can influence them.
"""
import ast
import hashlib
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

from . import tasks

RUNNER = Path(__file__).with_name("sandbox_runner.py")
TIMEOUT_S = 10
MAX_SOURCE_BYTES = 64 * 1024
ALLOWED_NODES = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If,
    ast.IfExp, ast.Compare, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Name,
    ast.Load, ast.Store, ast.Constant, ast.Call, ast.Expr, ast.Assign,
    ast.AugAssign, ast.While, ast.For, ast.Break, ast.Continue, ast.Pass,
    ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd,
    ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt,
    ast.GtE, ast.In, ast.NotIn, ast.Tuple, ast.List,
)
ALLOWED_CALLS = {"abs", "max", "min", "range", "int", "len"}


class InvalidCandidate(Exception):
    pass


def validate_source(source):
    """Reject anything outside a tiny pure-arithmetic subset of Python."""
    if len(source.encode()) > MAX_SOURCE_BYTES:
        raise InvalidCandidate("source too large")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise InvalidCandidate(f"syntax error: {exc.msg} (line {exc.lineno})")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise InvalidCandidate(f"forbidden construct: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise InvalidCandidate(f"forbidden name: {node.id}")
        if isinstance(node, ast.Call) and not (
                isinstance(node.func, ast.Name) and node.func.id in ALLOWED_CALLS):
            name = getattr(node.func, "id", type(node.func).__name__)
            raise InvalidCandidate(f"forbidden call target: {name}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, str, type(None))):
            raise InvalidCandidate("forbidden constant type")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "solve" for n in tree.body):
        raise InvalidCandidate("no top-level solve() function")


def _run_sandboxed(source, cases):
    nonce = secrets.token_hex(16)
    payload = json.dumps({"nonce": nonce, "source": source, "cases": cases})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(RUNNER)], input=payload,
            capture_output=True, text=True, timeout=TIMEOUT_S, cwd="/tmp")
    except subprocess.TimeoutExpired:
        raise InvalidCandidate(f"timeout after {TIMEOUT_S}s")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["no stderr"]
        raise InvalidCandidate(f"crashed (exit {proc.returncode}): {tail[0][:200]}")
    try:
        reply = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise InvalidCandidate("unparseable sandbox reply")
    outputs = reply.get("outputs")
    if reply.get("nonce") != nonce or not isinstance(outputs, list) or len(outputs) != len(cases):
        raise InvalidCandidate("sandbox reply failed authentication / shape check")
    return outputs


def _score(cases, outputs):
    per_task = {t: [0, 0] for t in tasks.TASK_IDS}
    for (task, x, y), got in zip(cases, outputs):
        per_task[task][1] += 1
        if type(got) is int and got == tasks.expected(task, x, y):
            per_task[task][0] += 1
    acc = {t: round(ok / n, 6) for t, (ok, n) in per_task.items()}
    return acc, round(sum(acc.values()) / len(acc), 6)


def evaluate_source(source):
    """Return a JSON-serialisable evaluation record (never raises)."""
    started = time.time()
    record = {"sha256": hashlib.sha256(source.encode()).hexdigest(),
              "valid": False, "error": None, "train_score": 0.0, "holdout_score": 0.0,
              "train": {}, "holdout": {}, "source_lines": source.count("\n")}
    try:
        validate_source(source)
        train_cases, hold_cases = tasks.case_list("train"), tasks.case_list("holdout")
        outputs = _run_sandboxed(source, train_cases + hold_cases)
        record["train"], record["train_score"] = _score(train_cases, outputs[:len(train_cases)])
        record["holdout"], record["holdout_score"] = _score(hold_cases, outputs[len(train_cases):])
        record["valid"] = True
    except InvalidCandidate as exc:
        record["error"] = str(exc)
    except Exception as exc:                       # judge must never crash the loop
        record["error"] = f"internal evaluation error: {type(exc).__name__}: {exc}"
    record["seconds"] = round(time.time() - started, 3)
    return record
