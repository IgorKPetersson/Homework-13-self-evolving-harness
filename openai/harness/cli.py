"""Command line entry point for reproducible evolution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import baseline, evolve, finalize, try_candidate_file, try_policy, verify
from .policy import Policy, Strategy
from .storage import exclusive_lock


def main() -> None:
    parser = argparse.ArgumentParser(description="Audited self-evolving packing harness")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("baseline")
    evolve_parser = sub.add_parser("evolve")
    evolve_parser.add_argument("--rounds", type=int, default=3)
    trial_parser = sub.add_parser("try")
    trial_parser.add_argument("candidate", type=Path)
    sub.add_parser("finalize")
    sub.add_parser("verify")
    sub.add_parser("demo")
    args = parser.parse_args()
    with exclusive_lock():
        if args.command == "baseline":
            data = {k: v.as_dict() for k, v in baseline().items()}
        elif args.command == "evolve":
            data = evolve(args.rounds)
        elif args.command == "try":
            data = try_candidate_file(args.candidate)
        elif args.command == "finalize":
            data = finalize()
        elif args.command == "verify":
            data = verify()
        else:
            base = {k: v.as_dict() for k, v in baseline().items()}
            rejection = try_policy(Policy((Strategy("ascending", "next"),)), "poor-strategy probe")
            rounds = evolve(3)
            final = finalize()
            check = verify()
            data = {"baseline": base, "probe": rejection, "rounds": rounds,
                    "final": final, "verification": check}
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
