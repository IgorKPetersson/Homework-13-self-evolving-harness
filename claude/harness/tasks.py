"""Benchmark definition: integer program-synthesis tasks.

The evolvable artifact is a solver exposing ``solve(task, x, y) -> int``.
Ground truth lives only here, inside the trusted harness. Candidates never
receive expected outputs; they only receive inputs.

Two disjoint case sets exist:
  * TRAIN   - visible to the proposer (the search procedure).
  * HOLDOUT - used only by the judge; the proposer never reads it.
"""
import random

TASKS = {
    "t1_square_plus_y": lambda x, y: x * x + y,
    "t2_linear": lambda x, y: 3 * x - 2 * y + 1,
    "t3_double_max": lambda x, y: max(x, y) * 2,
    "t4_xy_minus_x": lambda x, y: x * y - x,
    "t5_min_plus_sq": lambda x, y: min(x, y) + x * x,
    "t6_diff_squares": lambda x, y: (x + y) * (x - y),
}

TASK_IDS = sorted(TASKS)


def _cases(seed, n, lo, hi, exclude_box=None):
    rng = random.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        x, y = rng.randint(lo, hi), rng.randint(lo, hi)
        if exclude_box and abs(x) <= exclude_box and abs(y) <= exclude_box:
            continue
        if (x, y) in seen:
            continue
        seen.add((x, y))
        out.append((x, y))
    return out


TRAIN_INPUTS = _cases(seed=101, n=24, lo=-6, hi=6)
# Holdout is drawn from a wider range and excludes the train box, so a
# candidate that memorises training inputs cannot score on it.
HOLDOUT_INPUTS = _cases(seed=202, n=48, lo=-40, hi=40, exclude_box=6)


def expected(task, x, y):
    return TASKS[task](x, y)


def case_list(split):
    inputs = TRAIN_INPUTS if split == "train" else HOLDOUT_INPUTS
    return [(t, x, y) for t in TASK_IDS for (x, y) in inputs]
