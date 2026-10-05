"""Run the submitted source in a fresh, isolated workspace under openai/."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]


def main() -> None:
    target = SOURCE / "reproductions" / f"run-{uuid.uuid4().hex[:12]}"
    target.mkdir(parents=True)
    for directory in ("harness", "tests"):
        destination = target / directory
        destination.mkdir()
        for source in (SOURCE / directory).glob("*.py"):
            shutil.copy2(source, destination / source.name)
    env = os.environ.copy()
    env["HW13_SHARED_PATH"] = str(SOURCE.parent / "shared")
    steps = [
        ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("demo", [sys.executable, "-m", "harness.cli", "demo"]),
        ("verify", [sys.executable, "-m", "harness.cli", "verify"]),
    ]
    outcomes = {}
    for name, command in steps:
        result = subprocess.run(command, cwd=target, env=env, text=True,
                                capture_output=True, check=False)
        (target / f"{name}.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (target / f"{name}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        outcomes[name] = {"exit_code": result.returncode, "command": command}
        if result.returncode:
            break
    (target / "reproduction-summary.json").write_text(
        json.dumps({"workspace": str(target), "steps": outcomes}, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"workspace": str(target), "steps": outcomes}, indent=2))
    if any(item["exit_code"] for item in outcomes.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
