"""Closed-loop proposal, comparison, deterministic selection, and final evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluator import Result, evaluate, gate_reason
from .policy import MAX_STRATEGIES, ORDERS, PLACEMENTS, Policy, Strategy, parse_policy
from .storage import (CANDIDATE_DIR, RESULT_DIR, ROOT, append_audit, assert_trusted,
                      atomic_write, audit_records, commit, initialize, json_bytes,
                      load_state, read_policy, recover_pending, save_policy, trusted_manifest)


def _record_result(name: str, data: Any) -> None:
    atomic_write(RESULT_DIR / name, json_bytes(data))


def baseline() -> dict[str, Result]:
    state = initialize()
    policy = read_policy(state["active"])
    measurements = {split: evaluate(policy, split) for split in ("train", "gate")}
    path = RESULT_DIR / "baseline.json"
    if not path.exists():
        _record_result("baseline.json", {"active": state["active"],
                                         "measurements": {k: v.as_dict() for k, v in measurements.items()}})
        append_audit({"event": "baseline", "iteration": state["iteration"],
                      "baseline_score": measurements["gate"].excess_bins,
                      "candidate_score": None, "decision": "measured",
                      "reason": "baseline measured before candidate generation",
                      "policy_hash": state["active"],
                      "case_digest": measurements["gate"].case_digest})
    return measurements


def candidates(current: Policy) -> list[Policy]:
    all_strategies = [Strategy(order, placement) for order in ORDERS for placement in PLACEMENTS]
    proposals: set[Policy] = set()
    if len(current.strategies) < MAX_STRATEGIES:
        for strategy in all_strategies:
            if strategy not in current.strategies:
                proposals.add(Policy(current.strategies + (strategy,)))
    for index in range(len(current.strategies)):
        for strategy in all_strategies:
            if strategy not in current.strategies:
                next_strategies = list(current.strategies)
                next_strategies[index] = strategy
                proposals.add(Policy(tuple(next_strategies)))
    proposals.discard(current)
    return sorted(proposals, key=lambda p: p.canonical())


def try_policy(candidate: Policy, label: str = "manual") -> dict[str, Any]:
    state = initialize()
    recover_pending()
    state = load_state()
    current = read_policy(state["active"])
    before = trusted_manifest()
    baseline_gate = evaluate(current, "gate")
    sha = save_policy(candidate, CANDIDATE_DIR)
    try:
        candidate_gate = evaluate(candidate, "gate")
        assert_trusted(before)
        reason = gate_reason(baseline_gate, candidate_gate)
        accepted = reason.startswith("accepted:")
    except Exception as exc:
        candidate_gate = None
        reason = f"candidate evaluation failed: {type(exc).__name__}: {exc}"
        accepted = False
    iteration = state["iteration"] + 1
    if accepted:
        commit(candidate, iteration, baseline_gate.excess_bins, candidate_gate.excess_bins)
    else:
        append_audit({"event": "attempt", "iteration": iteration,
                      "baseline_score": baseline_gate.excess_bins,
                      "candidate_score": candidate_gate.excess_bins if candidate_gate else None,
                      "decision": "rejected", "reason": reason, "label": label,
                      "baseline_hash": state["active"], "candidate_hash": sha})
    result = {"iteration": iteration, "candidate_hash": sha,
              "baseline": baseline_gate.as_dict(),
              "candidate": candidate_gate.as_dict() if candidate_gate else None,
              "decision": "accepted" if accepted else "rejected", "reason": reason}
    _record_result(f"attempt-{len(audit_records()):04d}.json", result)
    return result


def try_candidate_file(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(CANDIDATE_DIR.resolve()):
        raise ValueError("candidate file must be inside candidates/")
    state = initialize()
    current = read_policy(state["active"])
    base = evaluate(current, "gate")
    try:
        candidate = parse_policy(resolved.read_bytes())
    except Exception as exc:
        result = {"iteration": state["iteration"] + 1, "baseline": base.as_dict(),
                  "candidate": None, "decision": "rejected",
                  "reason": f"invalid candidate: {type(exc).__name__}: {exc}"}
        append_audit({"event": "attempt", "iteration": result["iteration"],
                      "baseline_score": base.excess_bins, "candidate_score": None,
                      "decision": "rejected", "reason": result["reason"],
                      "candidate_file": str(resolved.relative_to(ROOT))})
        _record_result(f"attempt-{len(audit_records()):04d}.json", result)
        return result
    return try_policy(candidate, label=str(resolved.relative_to(ROOT)))


def evolve_round() -> dict[str, Any]:
    state = initialize()
    recover_pending()
    state = load_state()
    current = read_policy(state["active"])
    trusted_before = trusted_manifest()
    base_train = evaluate(current, "train")
    base_gate = evaluate(current, "gate")
    iteration = state["iteration"] + 1
    ranked: list[tuple[int, int, int, bytes, Policy, Result, str]] = []
    screened = 0
    for proposal in candidates(current):
        sha = save_policy(proposal, CANDIDATE_DIR)
        try:
            score = evaluate(proposal, "train")
            assert_trusted(trusted_before)
            gain = base_train.excess_bins - score.excess_bins
            if gain <= 0:
                screened += 1
                append_audit({"event": "screen", "iteration": iteration,
                              "baseline_score": base_train.excess_bins,
                              "candidate_score": score.excess_bins,
                              "decision": "rejected", "reason": "no training improvement",
                              "split": "train", "baseline_hash": state["active"],
                              "candidate_hash": sha})
            else:
                retains_current = all(strategy in proposal.strategies for strategy in current.strategies)
                ranked.append((-gain, 0 if retains_current else 1, len(proposal.strategies),
                               proposal.canonical(), proposal, score, sha))
        except Exception as exc:
            screened += 1
            append_audit({"event": "screen", "iteration": iteration,
                          "baseline_score": base_train.excess_bins, "candidate_score": None,
                          "decision": "rejected", "reason": f"evaluation failure: {type(exc).__name__}: {exc}",
                          "split": "train", "candidate_hash": sha})
    ranked.sort()
    if not ranked:
        summary = {"iteration": iteration, "decision": "stopped", "reason": "no training improvement",
                   "baseline_train": base_train.as_dict(), "baseline_gate": base_gate.as_dict(),
                   "screened": screened}
        append_audit({"event": "round", "iteration": iteration,
                      "baseline_score": base_train.excess_bins, "candidate_score": None,
                      "decision": "stopped", "reason": "no training improvement"})
        _record_result(f"round-{iteration:02d}.json", summary)
        return summary
    _, _, _, _, candidate, train_score, sha = ranked[0]
    for _, _, _, _, _, other_score, other_sha in ranked[1:]:
        append_audit({"event": "screen", "iteration": iteration,
                      "baseline_score": base_train.excess_bins,
                      "candidate_score": other_score.excess_bins, "decision": "not_selected",
                      "reason": "a stronger training proposal was selected",
                      "split": "train", "candidate_hash": other_sha})
    try:
        gate_score = evaluate(candidate, "gate")
        assert_trusted(trusted_before)
        reason = gate_reason(base_gate, gate_score)
        accepted = reason.startswith("accepted:")
    except Exception as exc:
        gate_score = None
        reason = f"candidate evaluation failed: {type(exc).__name__}: {exc}"
        accepted = False
    if accepted:
        commit(candidate, iteration, base_gate.excess_bins, gate_score.excess_bins)
    else:
        append_audit({"event": "attempt", "iteration": iteration,
                      "baseline_score": base_gate.excess_bins,
                      "candidate_score": gate_score.excess_bins if gate_score else None,
                      "decision": "rejected", "reason": reason, "split": "gate",
                      "baseline_hash": state["active"], "candidate_hash": sha})
    summary = {"iteration": iteration, "baseline_train": base_train.as_dict(),
               "candidate_train": train_score.as_dict(), "baseline_gate": base_gate.as_dict(),
               "candidate_gate": gate_score.as_dict() if gate_score else None,
               "candidate_hash": sha, "decision": "accepted" if accepted else "rejected",
               "reason": reason, "screened": screened,
               "positive_training_proposals": len(ranked)}
    _record_result(f"round-{iteration:02d}.json", summary)
    return summary


def evolve(rounds: int) -> list[dict[str, Any]]:
    if not 1 <= rounds <= 10:
        raise ValueError("rounds must be between 1 and 10")
    baseline()
    result = []
    for _ in range(rounds):
        round_result = evolve_round()
        result.append(round_result)
        if round_result["decision"] != "accepted":
            break
    return result


def finalize() -> dict[str, Any]:
    recover_pending()
    state = load_state()
    policy = read_policy(state["active"])
    results = {split: evaluate(policy, split).as_dict() for split in ("train", "gate", "holdout")}
    baseline_file = json.loads((RESULT_DIR / "baseline.json").read_text(encoding="utf-8"))
    baseline_holdout = evaluate(read_policy(baseline_file["active"]), "holdout").as_dict()
    final = {"active": state["active"], "iteration": state["iteration"],
             "baseline": baseline_file, "baseline_holdout": baseline_holdout,
             "final": results,
             "trusted_manifest": trusted_manifest(),
             "audit_head": audit_records()[-1]["hash"]}
    _record_result("final.json", final)
    return final


def verify() -> dict[str, Any]:
    records = audit_records()
    state = load_state()
    policy = read_policy(state["active"])
    final = json.loads((RESULT_DIR / "final.json").read_text(encoding="utf-8"))
    if final["active"] != state["active"] or final["audit_head"] != records[-1]["hash"]:
        raise ValueError("final artifact does not match state or audit")
    if final["trusted_manifest"] != trusted_manifest():
        raise ValueError("trusted manifest changed")
    for split in ("train", "gate", "holdout"):
        if final["final"][split] != evaluate(policy, split).as_dict():
            raise ValueError(f"{split} result cannot be reproduced")
    baseline_policy = read_policy(final["baseline"]["active"])
    for split in ("train", "gate"):
        if final["baseline"]["measurements"][split] != evaluate(baseline_policy, split).as_dict():
            raise ValueError(f"baseline {split} result cannot be reproduced")
    if final["baseline_holdout"] != evaluate(baseline_policy, "holdout").as_dict():
        raise ValueError("baseline holdout result cannot be reproduced")
    return {"verified": True, "active": state["active"], "audit_records": len(records),
            "scores": {split: final["final"][split]["excess_bins"]
                       for split in ("train", "gate", "holdout")}}
