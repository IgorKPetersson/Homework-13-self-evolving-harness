"""Deterministic cases and an independent exact bin-packing oracle."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from functools import lru_cache

CAPACITY = 100
FAMILIES = ("uniform", "complements", "triples", "large_small", "clustered", "small_first")
SPLIT_COUNTS = {"train": 12, "gate": 12, "holdout": 8}


@dataclass(frozen=True)
class Case:
    ident: str
    family: str
    items: tuple[int, ...]
    capacity: int = CAPACITY


def _rng(split: str, family: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"hw13-v1|{split}|{family}|{index}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


@lru_cache(maxsize=None)
def generate(split: str) -> tuple[Case, ...]:
    if split not in SPLIT_COUNTS:
        raise ValueError("unknown split")
    cases = []
    for family in FAMILIES:
        for index in range(SPLIT_COUNTS[split]):
            rng = _rng(split, family, index)
            if family == "uniform":
                values = [rng.randint(12, 85) for _ in range(rng.randint(10, 14))]
            elif family == "complements":
                values = []
                for _ in range(rng.randint(5, 7)):
                    value = rng.randint(20, 49)
                    values.extend((value, 100 - value))
                rng.shuffle(values)
            elif family == "triples":
                values = []
                for _ in range(rng.randint(3, 4)):
                    a = rng.randint(17, 36)
                    b = rng.randint(20, 45)
                    values.extend((a, b, 100 - a - b))
                rng.shuffle(values)
            elif family == "large_small":
                values = [rng.randint(51, 78) for _ in range(rng.randint(5, 7))]
                values += [rng.randint(20, 49) for _ in range(rng.randint(5, 7))]
                rng.shuffle(values)
            elif family == "clustered":
                center = rng.choice((25, 33, 40, 50, 66))
                values = [max(8, min(90, center + rng.randint(-8, 8))) for _ in range(rng.randint(10, 14))]
                rng.shuffle(values)
            else:
                values = [rng.randint(12, 38) for _ in range(rng.randint(5, 7))]
                values += [rng.randint(52, 82) for _ in range(rng.randint(5, 7))]
            cases.append(Case(f"{split}/{family}/{index:02d}", family, tuple(values)))
    return tuple(cases)


@lru_cache(maxsize=1024)
def optimum(items: tuple[int, ...], capacity: int = CAPACITY) -> int:
    """Exact O(n 2^n) subset DP. For equal bin counts, less fill dominates."""
    n = len(items)
    if n > 16 or any(not 0 < w <= capacity for w in items):
        raise ValueError("oracle domain exceeded")
    # A state is (bins used, load of final bin). The empty state has one empty bin.
    states: list[tuple[int, int] | None] = [None] * (1 << n)
    states[0] = (1, 0)
    for mask in range((1 << n) - 1):
        state = states[mask]
        if state is None:
            continue
        bins, load = state
        for i, weight in enumerate(items):
            bit = 1 << i
            if mask & bit:
                continue
            proposal = (bins, load + weight) if load + weight <= capacity else (bins + 1, weight)
            target = mask | bit
            if states[target] is None or proposal < states[target]:
                states[target] = proposal
    return states[-1][0] if n else 0  # type: ignore[index]
