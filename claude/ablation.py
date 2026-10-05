"""A/B ablation: feedback-adaptive proposer vs. non-adaptive proposer.

Each arm runs init + evolve in an isolated temporary state directory with the
same seeds and iteration budget, so the comparison is like-for-like.
Writes results/ablation.json.
"""
import json
import sys
import tempfile
from pathlib import Path

from harness import loop
from harness.store import Store

SEEDS = [1, 2, 3]
ITERATIONS = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def run_arm(seed, adapt):
    with tempfile.TemporaryDirectory() as d:
        loop.STORE, loop.LOG = Store(Path(d) / "state"), Path(d) / "log.jsonl"
        loop.init()
        rows, _, final = loop.evolve(ITERATIONS, seed, lam=300, adapt=adapt)
        return {"holdout": final["holdout_score"], "train": final["train_score"],
                "accepted": sum(r[3] == "ACCEPT" for r in rows)}


results = {"iterations": ITERATIONS, "seeds": SEEDS, "arms": {}}
for name, adapt in (("adaptive", True), ("non_adaptive", False)):
    runs = {str(s): run_arm(s, adapt) for s in SEEDS}
    mean = sum(r["holdout"] for r in runs.values()) / len(runs)
    results["arms"][name] = {"runs": runs, "mean_holdout": round(mean, 6)}
    print(f"{name:13s} mean holdout={mean:.4f} " +
          " ".join(f"s{s}={r['holdout']:.4f}" for s, r in runs.items()))
Path("results").mkdir(exist_ok=True)
Path("results/ablation.json").write_text(json.dumps(results, indent=2) + "\n")
