"""Trusted child-process runner. Executes ONE candidate against inputs only.

Protocol: parent writes {"nonce", "source", "cases"} as JSON on stdin; the
runner answers with a single JSON line {"nonce", "outputs"} on the original
stdout. Candidate code runs with a minimal builtins table and with stdout /
stderr redirected, so it cannot forge the reply. Expected outputs are never
sent to this process.
"""
import io
import json
import os
import sys

SAFE_BUILTINS = {"abs": abs, "max": max, "min": min, "range": range,
                 "int": int, "len": len, "True": True, "False": False, "None": None}


def _limit_resources():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))      # no file writes
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))      # no forking
    except (ImportError, ValueError, OSError):
        pass


def main():
    request = json.loads(sys.stdin.read())
    real_stdout = os.fdopen(os.dup(1), "w")
    _limit_resources()
    sys.stdout = sys.stderr = io.StringIO()
    namespace = {"__builtins__": SAFE_BUILTINS, "__name__": "candidate"}
    exec(compile(request["source"], "<candidate>", "exec"), namespace)
    solve = namespace.get("solve")
    if not callable(solve):
        raise SystemExit("candidate defines no callable solve()")
    outputs = []
    for task, x, y in request["cases"]:
        try:
            value = solve(task, x, y)
            outputs.append(value if type(value) is int else None)
        except Exception:                                 # case counts as wrong
            outputs.append(None)
    real_stdout.write(json.dumps({"nonce": request["nonce"], "outputs": outputs}) + "\n")
    real_stdout.flush()


if __name__ == "__main__":
    main()
