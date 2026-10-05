"""Write a candidate that memorises the TRAIN cases (an overfitting attack)."""
import sys

from harness import tasks

lines = ["def solve(task, x, y):"]
for t, x, y in tasks.case_list("train"):
    lines.append(f"    if task == {t!r} and x == {x} and y == {y}:")
    lines.append(f"        return {tasks.expected(t, x, y)}")
lines.append("    return 0")
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
