"""Explicit, deterministic accept/reject rule (a pure function).

Rules are applied in order; the first that fires decides:
  R1 REJECT  candidate invalid (syntax, forbidden construct, crash, timeout, bad reply)
  R2 REJECT  any single task's holdout accuracy drops       (no per-task regression)
  R3 REJECT  train score drops
  R4 ACCEPT  holdout score rises by more than EPS            (generalising improvement)
  R5 ACCEPT  holdout and train equal AND candidate strictly smaller (simplification)
  R6 REJECT  otherwise (no measurable improvement)
"""
EPS = 1e-9


def decide(current, candidate, current_size=None, candidate_size=None):
    if not candidate["valid"]:
        return "REJECT", f"R1 invalid candidate: {candidate['error']}"
    if not current["valid"]:
        return "ACCEPT", "R0 current version is invalid; any valid candidate wins"
    drops = [t for t, a in current["holdout"].items()
             if candidate["holdout"].get(t, 0.0) < a - EPS]
    if drops:
        return "REJECT", f"R2 per-task holdout regression on {drops}"
    if candidate["train_score"] < current["train_score"] - EPS:
        return "REJECT", (f"R3 train regression {current['train_score']:.4f} -> "
                          f"{candidate['train_score']:.4f}")
    if candidate["holdout_score"] > current["holdout_score"] + EPS:
        return "ACCEPT", (f"R4 holdout improved {current['holdout_score']:.4f} -> "
                          f"{candidate['holdout_score']:.4f}")
    if (abs(candidate["holdout_score"] - current["holdout_score"]) <= EPS
            and abs(candidate["train_score"] - current["train_score"]) <= EPS
            and None not in (current_size, candidate_size)
            and candidate_size < current_size):
        return "ACCEPT", f"R5 equal scores, simpler ({current_size} -> {candidate_size} nodes)"
    if candidate["train_score"] > current["train_score"] + EPS:
        return "REJECT", "R6 train-only gain without holdout gain (likely overfit)"
    return "REJECT", "R6 no measurable improvement"
