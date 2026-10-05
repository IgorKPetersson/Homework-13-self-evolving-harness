"""A deliberately small policy language with no executable candidate code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

ORDERS = ("input", "descending", "ascending", "alternating")
PLACEMENTS = ("first", "best", "worst", "next")
MAX_STRATEGIES = 4


@dataclass(frozen=True, order=True)
class Strategy:
    order: str
    placement: str

    def as_dict(self) -> dict[str, str]:
        return {"order": self.order, "placement": self.placement}


@dataclass(frozen=True)
class Policy:
    strategies: tuple[Strategy, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": 1, "strategies": [s.as_dict() for s in self.strategies]}

    def canonical(self) -> bytes:
        return (json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode()


def parse_policy(raw: bytes | str | dict[str, Any]) -> Policy:
    if isinstance(raw, (bytes, str)):
        if len(raw) > 4096:
            raise ValueError("candidate exceeds 4096 bytes")
        obj = json.loads(raw)
    else:
        obj = raw
    if not isinstance(obj, dict) or set(obj) != {"schema", "strategies"} or obj["schema"] != 1:
        raise ValueError("invalid policy schema")
    items = obj["strategies"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_STRATEGIES:
        raise ValueError("invalid strategy count")
    strategies = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"order", "placement"}:
            raise ValueError("invalid strategy shape")
        order, placement = item["order"], item["placement"]
        if not isinstance(order, str) or order not in ORDERS:
            raise ValueError("unknown order")
        if not isinstance(placement, str) or placement not in PLACEMENTS:
            raise ValueError("unknown placement")
        strategies.append(Strategy(order, placement))
    if len(set(strategies)) != len(strategies):
        raise ValueError("duplicate strategy")
    return Policy(tuple(strategies))


def pack(items: tuple[int, ...], capacity: int, strategy: Strategy) -> tuple[tuple[int, ...], ...]:
    indexed = list(enumerate(items))
    if strategy.order == "descending":
        indexed.sort(key=lambda x: (-x[1], x[0]))
    elif strategy.order == "ascending":
        indexed.sort(key=lambda x: (x[1], x[0]))
    elif strategy.order == "alternating":
        indexed.sort(key=lambda x: (-x[1], x[0]))
        indexed = indexed[::2] + indexed[1::2][::-1]

    bins: list[list[int]] = []
    loads: list[int] = []
    for index, weight in indexed:
        fitting = [j for j, load in enumerate(loads) if load + weight <= capacity]
        if strategy.placement == "next":
            chosen = len(loads) - 1 if loads and loads[-1] + weight <= capacity else None
        elif not fitting:
            chosen = None
        elif strategy.placement == "first":
            chosen = fitting[0]
        elif strategy.placement == "best":
            chosen = min(fitting, key=lambda j: (capacity - loads[j] - weight, j))
        else:
            chosen = max(fitting, key=lambda j: (capacity - loads[j] - weight, -j))
        if chosen is None:
            bins.append([index])
            loads.append(weight)
        else:
            bins[chosen].append(index)
            loads[chosen] += weight
    return tuple(tuple(b) for b in bins)


def run_policy(items: tuple[int, ...], capacity: int, policy: Policy) -> tuple[tuple[int, ...], ...]:
    choices = [pack(items, capacity, strategy) for strategy in policy.strategies]
    return min(choices, key=lambda bins: len(bins))
