"""The closed loop: measure -> propose -> evaluate -> compare -> accept/reject -> record."""
import json
from pathlib import Path

from . import audit, dsl, integrity, proposer, tasks
from .evaluator import evaluate_source
from .selection import decide
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
STORE = Store(ROOT / "state")
LOG = ROOT / "logs" / "evolution.jsonl"
RESULTS = ROOT / "results"


class HarnessError(Exception):
    pass


def _size(genome):
    return dsl.genome_size(genome) if genome else None


def _brief(ev):
    return {k: ev[k] for k in ("valid", "error", "train_score", "holdout_score", "sha256")}


def preflight():
    ok, msg = integrity.check_harness()
    if not ok:
        audit.append(LOG, "integrity_violation", detail=msg)
        raise HarnessError(f"refusing to run: {msg}")
    ok, msg = audit.verify(LOG)
    if not ok:
        raise HarnessError(f"refusing to run: audit log tampered ({msg})")


def init():
    if STORE.initialized():
        raise HarnessError("state already initialised")
    preflight()
    genome = {t: 0 for t in tasks.TASK_IDS}              # trivial seed program
    source = dsl.render_solver(genome)
    ev = evaluate_source(source)
    d = STORE.save_candidate("seed", source, genome, ev)
    version = STORE.promote(d)
    audit.append(LOG, "init", version=version, evaluation=_brief(ev),
                 harness_manifest=integrity.manifest_digest(),
                 shared_fingerprint=integrity.shared_fingerprint())
    return version, ev


def load_current():
    cur, note = STORE.current()
    if note:
        audit.append(LOG, "recovery", detail=note)
    return cur


def measure_baseline():
    """Freshly re-evaluate the active version with the judge and cross-check it
    against the score recorded when it was accepted (determinism/tamper check)."""
    cur = load_current()
    ev = evaluate_source(cur["source"])
    stored = cur["eval"]
    if (ev["sha256"], ev["train_score"], ev["holdout_score"]) != (
            stored["sha256"], stored["train_score"], stored["holdout_score"]):
        audit.append(LOG, "baseline_mismatch", version=cur["version"],
                     fresh=_brief(ev), stored=_brief(stored))
        raise HarnessError("re-measured baseline differs from recorded score")
    return cur, ev


def next_iteration():
    return 1 + sum(e["event"] == "iteration" for e in audit.read(LOG))


def attempt(cur, cur_ev, source, genome, origin, note, params=None):
    """Evaluate one candidate against the current version and record the decision."""
    it = next_iteration()
    cand_ev = evaluate_source(source)
    cand_dir = STORE.save_candidate(f"iter_{it:04d}", source, genome, cand_ev)
    decision, reason = decide(cur_ev, cand_ev, _size(cur["genome"]), _size(genome))
    new_version = STORE.promote(cand_dir) if decision == "ACCEPT" else None
    audit.append(LOG, "iteration", iteration=it, origin=origin, proposer_note=note, proposer_params=params,
                  current_version=cur["version"],
                  baseline_score=cur_ev["holdout_score"], baseline_train=cur_ev["train_score"],
                  candidate_score=cand_ev["holdout_score"], candidate_train=cand_ev["train_score"],
                  candidate_valid=cand_ev["valid"], candidate_error=cand_ev["error"],
                  candidate_sha256=cand_ev["sha256"], decision=decision, reason=reason,
                  new_version=new_version, candidate_dir=str(cand_dir.relative_to(STORE.root.parent)))
    return it, decision, reason, cand_ev


def proposer_history():
    """Past proposer decisions (focus task, decision) - the feedback signal."""
    return [(e["proposer_params"]["focus"], e["decision"]) for e in audit.read(LOG)
            if e["event"] == "iteration" and e.get("proposer_params")]


def evolve(iterations, seed, lam, adapt=True):
    preflight()
    shared_before = integrity.shared_fingerprint()
    cur, cur_ev = measure_baseline()
    audit.append(LOG, "run_start", seed=seed, lam=lam, iterations=iterations, adapt=adapt,
                 version=cur["version"], baseline_score=cur_ev["holdout_score"],
                 baseline_train=cur_ev["train_score"],
                 harness_manifest=integrity.manifest_digest(), shared_fingerprint=shared_before)
    rows = []
    for _ in range(iterations):
        it = next_iteration()
        genome, note, params = proposer.propose(cur["genome"] or {}, seed=f"{seed}:{it}",
                                                lam=lam, history=proposer_history() if adapt else ())
        _, decision, reason, cand_ev = attempt(cur, cur_ev, dsl.render_solver(genome),
                                               genome, "proposer", note, params)
        rows.append((it, cur_ev["holdout_score"], cand_ev["holdout_score"], decision, reason))
        if decision == "ACCEPT":
            cur, cur_ev = measure_baseline()       # new champion, re-measured by the judge
    if integrity.shared_fingerprint() != shared_before:
        audit.append(LOG, "integrity_violation", detail="shared directory changed during run")
        raise HarnessError("shared challenge directory changed during run")
    audit.append(LOG, "run_end", version=cur["version"], final_score=cur_ev["holdout_score"],
                 final_train=cur_ev["train_score"])
    return rows, cur, cur_ev


def submit(path, origin="external"):
    """Evaluate an externally supplied solver file as a candidate."""
    preflight()
    cur, cur_ev = measure_baseline()
    source = Path(path).read_text(errors="replace")
    return attempt(cur, cur_ev, source, None, f"{origin}:{Path(path).name}", "submitted file")


def write_report():
    entries = audit.read(LOG)
    its = [e for e in entries if e["event"] == "iteration"]
    cur = load_current()
    summary = {
        "current_version": cur["version"], "current_eval": cur["eval"],
        "iterations": len(its),
        "accepted": sum(e["decision"] == "ACCEPT" for e in its),
        "rejected": sum(e["decision"] == "REJECT" for e in its),
        "invalid_rejected": sum(not e["candidate_valid"] for e in its),
        "audit_log": dict(zip(("ok", "message"), audit.verify(LOG))),
        "harness_integrity": dict(zip(("ok", "message"), integrity.check_harness())),
        "versions": STORE.list_versions(),
    }
    init_ev = next((e["evaluation"] for e in entries if e["event"] == "init"), None)
    summary["initial_eval"] = init_ev
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = ["# Evolution report (generated from logs/evolution.jsonl)", "",
             f"- Initial holdout score: {init_ev and init_ev['holdout_score']}",
             f"- Final version: {cur['version']} holdout={cur['eval']['holdout_score']} "
             f"train={cur['eval']['train_score']}",
             f"- Iterations: {summary['iterations']}, accepted: {summary['accepted']}, "
             f"rejected: {summary['rejected']} (of which invalid: {summary['invalid_rejected']})",
             f"- Audit log: {summary['audit_log']['message']}", "",
             "| iter | origin | baseline | candidate | decision | reason |",
             "|---:|---|---:|---:|---|---|"]
    for e in its:
        lines.append(f"| {e['iteration']} | {e['origin']} | {e['baseline_score']:.4f} | "
                     f"{e['candidate_score']:.4f} | {e['decision']} | "
                     f"{e['reason'].replace('|', '/')[:110]} |")
    (RESULTS / "evolution_report.md").write_text("\n".join(lines) + "\n")
    return summary
