"""CLI: python -m harness <command>"""
import argparse
import json
import sys

from . import audit, integrity, loop


def main(argv=None):
    p = argparse.ArgumentParser(prog="harness", description="Self-evolving harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock", help="pin SHA-256 of trusted harness files")
    sub.add_parser("init", help="create and measure the seed version")
    sub.add_parser("baseline", help="re-measure the current version")
    ev = sub.add_parser("evolve", help="run evolution iterations")
    ev.add_argument("--iterations", type=int, default=30)
    ev.add_argument("--seed", type=int, default=13)
    ev.add_argument("--lam", type=int, default=300)
    ev.add_argument("--no-adapt", action="store_true", help="disable feedback-driven proposer")
    sb = sub.add_parser("submit", help="evaluate an external candidate solver file")
    sb.add_argument("path")
    sub.add_parser("rollback", help="repoint CURRENT to the previous version")
    sub.add_parser("verify", help="verify audit log chain and harness integrity")
    sub.add_parser("report", help="write results/summary.json and evolution_report.md")
    a = p.parse_args(argv)
    try:
        if a.cmd == "lock":
            integrity.lock()
            audit.append(loop.LOG, "harness_locked", manifest=integrity.manifest_digest())
            print("harness locked:", integrity.manifest_digest())
        elif a.cmd == "init":
            version, ev_ = loop.init()
            print(f"{version}: holdout={ev_['holdout_score']} train={ev_['train_score']}")
        elif a.cmd == "baseline":
            cur, ev_ = loop.measure_baseline()
            audit.append(loop.LOG, "baseline", version=cur["version"],
                         baseline_score=ev_["holdout_score"], baseline_train=ev_["train_score"])
            print(json.dumps({"version": cur["version"], **ev_}, indent=2))
        elif a.cmd == "evolve":
            rows, cur, ev_ = loop.evolve(a.iterations, a.seed, a.lam, adapt=not a.no_adapt)
            for it, b, c, d, r in rows:
                print(f"iter {it:3d}  baseline={b:.4f}  candidate={c:.4f}  {d:6s}  {r}")
            print(f"final {cur['version']}: holdout={ev_['holdout_score']} train={ev_['train_score']}")
        elif a.cmd == "submit":
            it, d, r, ev_ = loop.submit(a.path)
            print(f"iter {it}: {d} - {r} (holdout={ev_['holdout_score']})")
        elif a.cmd == "rollback":
            old, new = loop.STORE.rollback()
            audit.append(loop.LOG, "rollback", from_version=old, to_version=new)
            print(f"rolled back {old} -> {new}")
        elif a.cmd == "verify":
            checks = [audit.verify(loop.LOG), integrity.check_harness()]
            for ok, msg in checks:
                print(("OK   " if ok else "FAIL ") + msg)
            return 0 if all(ok for ok, _ in checks) else 1
        elif a.cmd == "report":
            print(json.dumps(loop.write_report(), indent=2, sort_keys=True))
    except (loop.HarnessError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
