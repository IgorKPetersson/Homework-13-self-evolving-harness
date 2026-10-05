"""Trusted measurement, feasibility checks, and comparable result records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .benchmark import Case, generate, optimum
from .policy import Policy, run_policy


def check_packing(case: Case, bins: tuple[tuple[int, ...], ...]) -> None:
    flat = [index for group in bins for index in group]
    if len(flat) != len(case.items) or sorted(flat) != list(range(len(case.items))):
        raise ValueError(f"missing or duplicated item: {case.ident}")
    if any(not group or sum(case.items[i] for i in group) > case.capacity for group in bins):
        raise ValueError(f"overfull or empty bin: {case.ident}")


@dataclass(frozen=True)
class Result:
    split: str
    policy_hash: str
    cases: int
    total_bins: int
    optimal_bins: int
    excess_bins: int
    family_excess: dict[str, int]
    case_digest: str

    def as_dict(self) -> dict[str, Any]:
        return vars(self).copy()


def evaluate(policy: Policy, split: str, cases: tuple[Case, ...] | None = None) -> Result:
    cases = generate(split) if cases is None else cases
    family_excess: dict[str, int] = {}
    total = ideal = 0
    canonical_cases = []
    for case in cases:
        bins = run_policy(case.items, case.capacity, policy)
        check_packing(case, bins)
        exact = optimum(case.items, case.capacity)
        if len(bins) < exact:
            raise AssertionError("oracle or packing validator is inconsistent")
        total += len(bins)
        ideal += exact
        family_excess[case.family] = family_excess.get(case.family, 0) + len(bins) - exact
        canonical_cases.append((case.ident, case.capacity, case.items, exact))
    case_digest = hashlib.sha256(json.dumps(canonical_cases, separators=(",", ":")).encode()).hexdigest()
    policy_hash = hashlib.sha256(policy.canonical()).hexdigest()
    return Result(split, policy_hash, len(cases), total, ideal, total - ideal, family_excess, case_digest)


def gate_reason(current: Result, candidate: Result) -> str:
    if current.split != candidate.split or current.case_digest != candidate.case_digest:
        return "evaluation mismatch"
    if candidate.excess_bins >= current.excess_bins:
        return "no strict improvement in excess bins"
    regressed = [name for name, score in current.family_excess.items()
                 if candidate.family_excess.get(name, 0) > score]
    if regressed:
        return "family regression: " + ", ".join(regressed)
    return "accepted: lower excess bins and no family regression"
