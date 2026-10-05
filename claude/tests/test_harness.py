"""Unit and integration tests. Run: python -m unittest discover -s tests -v

All tests that touch state use a temporary directory, never the real state/.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from harness import audit, dsl, evaluator, integrity, loop, tasks
from harness.selection import decide
from harness.store import Store

PERFECT = '''
def solve(task, x, y):
    if task == "t1_square_plus_y":
        return x * x + y
    if task == "t2_linear":
        return 3 * x - 2 * y + 1
    if task == "t3_double_max":
        return max(x, y) * 2
    if task == "t4_xy_minus_x":
        return x * y - x
    if task == "t5_min_plus_sq":
        return min(x, y) + x * x
    return (x + y) * (x - y)
'''


def ev(train, hold, holdout=None, valid=True):
    return {"valid": valid, "error": None if valid else "boom", "train_score": train,
            "holdout_score": hold, "holdout": holdout or {"a": hold}}


class TestEvaluator(unittest.TestCase):
    def test_perfect_solver_scores_one(self):
        r = evaluator.evaluate_source(PERFECT)
        self.assertTrue(r["valid"], r["error"])
        self.assertEqual((r["train_score"], r["holdout_score"]), (1.0, 1.0))

    def test_static_validation_rejects_attacks(self):
        attacks = {"import os\ndef solve(t,x,y): return 0": "Import",
                   "def solve(t,x,y): return ().__class__": "Attribute",
                   "def solve(t,x,y): return __import__('os')": "__import__",
                   "def solve(t,x,y): return open('f')": "call",
                   "def solve(t,x,y) return 0": "syntax",
                   "def other(t,x,y): return 0": "solve",
                   "def solve(t,x,y): return eval('1')": "call"}
        for src, word in attacks.items():
            r = evaluator.evaluate_source(src)
            self.assertFalse(r["valid"], src)
            self.assertIn(word.lower(), r["error"].lower(), src)

    def test_infinite_loop_is_contained(self):
        r = evaluator.evaluate_source("def solve(t,x,y):\n    while True:\n        x = x + 1\n")
        self.assertFalse(r["valid"])
        self.assertLess(r["seconds"], evaluator.TIMEOUT_S + 5)

    def test_non_int_outputs_score_zero(self):
        r = evaluator.evaluate_source("def solve(t,x,y):\n    return True\n")
        self.assertTrue(r["valid"])
        self.assertEqual(r["holdout_score"], 0.0)

    def test_generated_solver_matches_in_process_eval(self):
        tree = ["add", ["mul", "x", "x"], "y"]
        r = evaluator.evaluate_source(dsl.render_solver({"t1_square_plus_y": tree}))
        self.assertEqual(r["holdout"]["t1_square_plus_y"], 1.0)
        self.assertEqual(dsl.evaluate(tree, 3, 4), 13)

    def test_holdout_disjoint_from_train(self):
        self.assertFalse(set(tasks.TRAIN_INPUTS) & set(tasks.HOLDOUT_INPUTS))


class TestSelection(unittest.TestCase):
    def test_rules(self):
        cur = ev(0.5, 0.5)
        self.assertTrue(decide(cur, ev(0, 0, valid=False))[1].startswith("R1"))
        self.assertTrue(decide(cur, ev(0.6, 0.4))[1].startswith("R2"))
        self.assertTrue(decide(cur, ev(0.4, 0.6))[1].startswith("R3"))
        self.assertEqual(decide(cur, ev(0.5, 0.6))[0], "ACCEPT")
        self.assertEqual(decide(cur, ev(0.5, 0.5), 10, 9)[0], "ACCEPT")
        self.assertEqual(decide(cur, ev(0.5, 0.5), 10, 10)[0], "REJECT")
        self.assertIn("overfit", decide(cur, ev(0.9, 0.5))[1])

    def test_per_task_regression_blocks_net_gain(self):
        cur = ev(0.5, 0.5, {"a": 1.0, "b": 0.0})
        cand = ev(0.5, 0.75, {"a": 0.5, "b": 1.0})
        self.assertEqual(decide(cur, cand)[0], "REJECT")

    def test_deterministic(self):
        cur, cand = ev(0.5, 0.5), ev(0.5, 0.6)
        self.assertEqual({decide(cur, cand) for _ in range(20)}, {decide(cur, cand)})


class TempStateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = (loop.STORE, loop.LOG, loop.RESULTS)
        loop.STORE, loop.LOG, loop.RESULTS = (Store(self.tmp / "state"),
                                              self.tmp / "evolution.jsonl", self.tmp / "results")

    def tearDown(self):
        loop.STORE, loop.LOG, loop.RESULTS = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestLoop(TempStateCase):
    def test_evolution_never_regresses_and_logs_everything(self):
        _, first = loop.init()
        rows, cur, last = loop.evolve(iterations=4, seed=7, lam=150)
        self.assertGreaterEqual(last["holdout_score"], first["holdout_score"])
        its = [e for e in audit.read(loop.LOG) if e["event"] == "iteration"]
        self.assertEqual(len(its), 4)
        for e in its:
            for key in ("iteration", "baseline_score", "candidate_score", "decision",
                        "reason", "timestamp"):
                self.assertIn(key, e)
        self.assertTrue(audit.verify(loop.LOG)[0])

    def test_invalid_candidate_keeps_last_known_good(self):
        loop.init()
        before = loop.STORE.pointer.read_text()
        bad = self.tmp / "bad.py"
        bad.write_text("import os\ndef solve(t,x,y): return 0\n")
        _, decision, reason, _ = loop.submit(bad)
        self.assertEqual(decision, "REJECT")
        self.assertTrue(reason.startswith("R1"))
        self.assertEqual(loop.STORE.pointer.read_text(), before)

    def test_external_improvement_is_accepted_then_rollback(self):
        loop.init()
        good = self.tmp / "good.py"
        good.write_text(PERFECT)
        self.assertEqual(loop.submit(good)[1], "ACCEPT")
        self.assertEqual(loop.load_current()["eval"]["holdout_score"], 1.0)
        self.assertEqual(loop.STORE.rollback(), ("v0002", "v0001"))

    def test_corrupted_current_version_recovers_to_previous(self):
        loop.init()
        good = self.tmp / "good.py"
        good.write_text(PERFECT)
        loop.submit(good)
        (loop.STORE.versions / "v0002" / "solver.py").write_text("def solve(t,x,y): return 1\n")
        cur = loop.load_current()
        self.assertEqual(cur["version"], "v0001")
        self.assertIn("recovery", [e["event"] for e in audit.read(loop.LOG)])

    def test_tampered_baseline_score_is_detected(self):
        loop.init()
        meta = loop.STORE.versions / "v0001" / "eval.json"
        data = json.loads(meta.read_text())
        data["holdout_score"] = 0.99
        meta.write_text(json.dumps(data))
        with self.assertRaises(loop.HarnessError):
            loop.measure_baseline()


class TestProposer(unittest.TestCase):
    def test_reject_streak_lowers_focus_and_raises_effort(self):
        from harness import proposer
        hist = [("t2_linear", "REJECT")] * 4 + [("t1_square_plus_y", "ACCEPT")]
        self.assertEqual(proposer.reject_streaks(hist)["t2_linear"], 4)
        self.assertEqual(proposer.reject_streaks(hist)["t1_square_plus_y"], 0)
        genome = {t: 0 for t in tasks.TASK_IDS}
        focuses = [proposer.propose(genome, s, lam=5, history=hist)[2]["focus"]
                   for s in range(60)]
        self.assertLess(focuses.count("t2_linear"), 60 / 6)

    def test_proposal_is_deterministic(self):
        from harness import proposer
        genome = {t: 0 for t in tasks.TASK_IDS}
        self.assertEqual(proposer.propose(genome, "s:1", lam=50),
                         proposer.propose(genome, "s:1", lam=50))


class TestAuditAndIntegrity(unittest.TestCase):
    def test_audit_tampering_detected(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log.jsonl"
            for i in range(3):
                audit.append(log, "iteration", decision="REJECT", n=i)
            self.assertTrue(audit.verify(log)[0])
            lines = log.read_text().splitlines()
            log.write_text("\n".join([lines[0], lines[1].replace("REJECT", "ACCEPT"), lines[2]]) + "\n")
            self.assertFalse(audit.verify(log)[0])
            log.write_text("\n".join([lines[0], lines[2]]) + "\n")
            self.assertFalse(audit.verify(log)[0])

    def test_modified_evaluator_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "harness"
            shutil.copytree(integrity.HARNESS_DIR, copy)
            saved = integrity.HARNESS_DIR, integrity.MANIFEST
            integrity.HARNESS_DIR, integrity.MANIFEST = copy, copy / "MANIFEST.json"
            try:
                integrity.lock()
                self.assertTrue(integrity.check_harness()[0])
                p = copy / "selection.py"
                p.write_text(p.read_text().replace('return "REJECT"', 'return "ACCEPT"'))
                ok, msg = integrity.check_harness()
                self.assertFalse(ok)
                self.assertIn("selection.py", msg)
            finally:
                integrity.HARNESS_DIR, integrity.MANIFEST = saved


if __name__ == "__main__":
    unittest.main()
