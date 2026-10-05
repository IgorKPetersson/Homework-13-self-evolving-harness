from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness import storage
from harness.benchmark import CAPACITY, Case, generate, optimum
from harness.evaluator import Result, check_packing, evaluate, gate_reason
from harness.policy import ORDERS, PLACEMENTS, Policy, Strategy, parse_policy, run_policy


def brute_optimum(items: tuple[int, ...], capacity: int) -> int:
    """Independent exhaustive oracle for short instances."""
    best = len(items)

    def visit(index: int, loads: list[int]) -> None:
        nonlocal best
        if index == len(items):
            best = min(best, len(loads))
            return
        if len(loads) >= best:
            return
        seen = set()
        for j, load in enumerate(loads):
            if load in seen or load + items[index] > capacity:
                continue
            seen.add(load)
            loads[j] += items[index]
            visit(index + 1, loads)
            loads[j] -= items[index]
        loads.append(items[index])
        visit(index + 1, loads)
        loads.pop()

    if not items:
        return 0
    visit(0, [])
    return best


class OracleTests(unittest.TestCase):
    def test_exact_oracle_against_independent_search(self) -> None:
        rng = random.Random(418)
        for _ in range(60):
            items = tuple(rng.randint(1, 30) for _ in range(rng.randint(1, 8)))
            self.assertEqual(optimum(items, 40), brute_optimum(items, 40))

    def test_splits_are_distinct_and_all_strategies_are_feasible(self) -> None:
        self.assertTrue(set(c.ident for c in generate("train")).isdisjoint(
            c.ident for c in generate("gate")))
        self.assertTrue(set(c.ident for c in generate("gate")).isdisjoint(
            c.ident for c in generate("holdout")))
        for case in generate("holdout"):
            for order in ORDERS:
                for placement in PLACEMENTS:
                    policy = Policy((Strategy(order, placement),))
                    check_packing(case, run_policy(case.items, case.capacity, policy))


class IntegrityTests(unittest.TestCase):
    def test_data_only_policy_validation(self) -> None:
        bad = [
            {"schema": 1, "strategies": [{"order": "input", "placement": "first", "exec": "x"}]},
            {"schema": 1, "strategies": [{"order": "input", "placement": "first"}], "score": 0},
            {"schema": 1, "strategies": []},
            {"schema": 1, "strategies": [{"order": "input", "placement": "first"}] * 2},
            {"schema": 1, "strategies": [{"order": "../shared", "placement": "first"}]},
        ]
        for candidate in bad:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                parse_policy(candidate)

    def test_packing_validator_rejects_cheating(self) -> None:
        case = Case("fake", "test", (60, 60), CAPACITY)
        for bins in (((0, 1),), ((0,),), ((0,), (0,), (1,))):
            with self.subTest(bins=bins), self.assertRaises(ValueError):
                check_packing(case, bins)

    def test_gate_requires_strict_gain_and_family_safety(self) -> None:
        common = dict(split="gate", policy_hash="x", cases=2, total_bins=9,
                      optimal_bins=7, case_digest="fixed")
        current = Result(**common, excess_bins=2, family_excess={"a": 1, "b": 1})
        good = Result(**common, excess_bins=1, family_excess={"a": 0, "b": 1})
        bad = Result(**common, excess_bins=1, family_excess={"a": 2, "b": -1})
        self.assertTrue(gate_reason(current, good).startswith("accepted:"))
        self.assertIn("family regression", gate_reason(current, bad))
        self.assertIn("no strict improvement", gate_reason(current, current))

    def test_interrupted_commit_preserves_last_good(self) -> None:
        with tempfile.TemporaryDirectory(dir=storage.ROOT) as name:
            root = Path(name)
            with patch.multiple(storage, ROOT=root, STATE=root / "state.json",
                                AUDIT=root / "audit" / "evolution.jsonl",
                                MANIFEST=root / "audit" / "trusted-manifest.json",
                                VERSION_DIR=root / "versions", CANDIDATE_DIR=root / "candidates",
                                RESULT_DIR=root / "results"), patch.object(storage, "trusted_manifest", return_value={"test": "fixed"}):
                state = storage.initialize()
                baseline_hash = state["active"]
                improved = Policy((Strategy("input", "first"), Strategy("descending", "best")))
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    storage.commit(improved, 1, 55, 13, fail_after_intent=True)
                self.assertEqual(storage.load_state()["active"], baseline_hash)
                storage.recover_pending()
                self.assertEqual(storage.audit_records()[-1]["decision"], "rejected")
                self.assertEqual(storage.load_state()["active"], baseline_hash)
                new_hash = storage.commit(improved, 1, 55, 13)
                self.assertEqual(storage.load_state()["active"], new_hash)
                self.assertNotEqual(new_hash, baseline_hash)


if __name__ == "__main__":
    unittest.main()
