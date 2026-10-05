# Self-Evolving Harness (HW13, Claude)

A closed-loop system that improves a program under test and keeps a change only
if an independent, sandboxed judge measures a real improvement:

```
measure -> propose -> evaluate -> compare -> accept/reject -> record
```

It uses only the Python 3.12 standard library, needs no network or API keys, and every run is deterministic.

## Reproduce from a clean container

From the repository root (the directory containing `docker-compose.yml`):

```bash
docker compose build claude
docker compose run --rm claude bash run_all.sh        # ~1-2 min
```

Or, inside an already running container:

```bash
docker exec -it -w /workspace/claude hw13-claude bash run_all.sh
```

`run_all.sh` deletes `state/`, `logs/` and `results/` and regenerates all of them. You can set
`ITERATIONS` (default 60) and `SEED` (default 13). Individual commands:

| Command | Purpose |
|---|---|
| `python -m harness lock` | pin the SHA-256 of every trusted harness file (`harness/MANIFEST.json`) |
| `python -m harness init` | create and measure the seed version `v0001` |
| `python -m harness baseline` | re-measure the active version with the judge |
| `python -m harness evolve --iterations N --seed S [--lam L] [--no-adapt]` | run evolution |
| `python -m harness submit FILE` | evaluate an externally written candidate with the same rule |
| `python -m harness rollback` | move `CURRENT` back to the previous accepted version |
| `python -m harness verify` | check the audit hash chain and the harness integrity |
| `python -m harness report` | write `results/summary.json` and `results/evolution_report.md` |
| `python -m unittest discover -s tests -v` | 18 unit and integration tests |
| `python ablation.py 60` | A/B test of the adaptive and non-adaptive proposer |

## What evolves

The artifact under evolution is a **solver program** (`solve(task, x, y) -> int`) for six
integer program-synthesis tasks (`harness/tasks.py`), for example `x*x + y` and `(x+y)*(x-y)`.
The proposer represents a solver as a genome of expression trees (`harness/dsl.py`) and renders it
to real Python source. The judge only ever sees that source code, and it applies exactly the same
procedure to externally submitted solvers.

## Architecture

| Module | Role | Trust |
|---|---|---|
| `tasks.py` | Ground truth, the **train** cases (24 inputs × 6 tasks) and the disjoint **holdout** cases (48 inputs × 6 tasks, wider range, train box excluded) | trusted |
| `proposer.py` | (1+λ) genetic programming that searches on **train only**. It adapts to the judge's past decisions: a task with a reject streak gets exponentially lower focus weight, effort λ doubles (up to 8×), and after 3 straight rejects it restarts from random trees | untrusted output |
| `evaluator.py` | The judge. It runs an AST whitelist, then executes the candidate in a child process, then **scores in the parent** | trusted |
| `sandbox_runner.py` | The child process. It runs with `python -I -S -B`, minimal builtins, and rlimits on CPU, memory, file writes and forking. stdout is redirected, and the reply is authenticated with a per-run random nonce | trusted |
| `selection.py` | The pure, deterministic accept/reject rule | trusted |
| `store.py` | Immutable versions `state/versions/vNNNN`, an archive of every candidate in `state/candidates/`, an atomic `CURRENT` pointer, and corruption recovery to the last known good version | trusted |
| `audit.py` | Append-only JSONL log in which each entry includes the hash of the previous one | trusted |
| `integrity.py` | Hash manifest of the harness files plus a fingerprint of `/workspace/shared` | trusted |
| `loop.py` | Orchestration: preflight, baseline, iterations, promotion, report | trusted |

### Accept/reject rule (`harness/selection.py`)

The rules are checked in order and the first one that matches decides:

1. **R1 REJECT**: the candidate is invalid (syntax error, forbidden construct, crash, timeout, or a sandbox reply that is forged or malformed).
2. **R2 REJECT**: the holdout accuracy of *any single task* drops. A net gain does not excuse a regression on one task.
3. **R3 REJECT**: the train score drops.
4. **R4 ACCEPT**: the holdout score rises by more than 1e-9.
5. **R5 ACCEPT**: all scores are equal and the candidate has strictly fewer nodes (a simplification).
6. **R6 REJECT**: anything else. If only the train score improved, the reason is logged as "likely overfit".

The baseline and the candidate go through the same `evaluate_source()` call. The current version is
**re-measured** before every run and after every promotion. If the fresh score differs from the score
stored when that version was accepted, the run aborts. This catches a tampered `eval.json` or a
non-deterministic judge.

### Safety and rollback

- Candidates are evaluated in a separate process in `/tmp`. The current version is never touched until
  `os.replace` atomically moves the `CURRENT` pointer to a fully written version directory.
- Every accepted version stays on disk unchanged, and `rollback` repoints `CURRENT` to the previous one.
- If the solver file of the active version no longer matches its recorded hash, the harness falls back
  to the newest intact version and logs a `recovery` event.
- Any exception in the judge becomes an invalid-candidate record. The loop never crashes because of a
  candidate.

### Evaluator-manipulation defenses

| Attack | Defense | Evidence |
|---|---|---|
| Edit the judge, benchmark or rule | The SHA-256 manifest is checked before every command. A mismatch makes the harness refuse to run and logs an `integrity_violation` event | `results/tamper_demo.txt`, `test_modified_evaluator_is_detected` |
| Candidate deletes or edits harness files | AST whitelist (no import, attribute or dunder access, only `abs/max/min/range/int/len` may be called), minimal builtins, `RLIMIT_FSIZE=0` | `adversarial/03_tamper_evaluator.py` → R1 |
| Sandbox escape through `().__class__...` | Attribute access is forbidden | `adversarial/04_sandbox_escape.py` → R1 |
| Print a fake score | The score is computed in the parent from raw outputs, the candidate's stdout is redirected, and the reply needs the nonce | `sandbox_runner.py` |
| Hang the judge | `RLIMIT_CPU` of 4 s plus a 10 s wall-clock timeout | `adversarial/02_infinite_loop.py` → R1 |
| Return `True`/floats to match by equality | Only an exact `int` type counts | `adversarial/06_wrong_types.py` → R2 |
| Memorize the evaluation cases | Holdout inputs are disjoint from train and drawn from a wider range | `adversarial/07_memorizer.py`: train 1.0, holdout ≈0 → R2 |
| Rewrite history | Hash-chained audit log. `verify` reports an edited, deleted or reordered entry | `test_audit_tampering_detected` |
| Inflate a stored score | Fresh re-measurement is compared with the stored score | `test_tampered_baseline_score_is_detected` |
| Change the shared evaluator | `/workspace/shared` is mounted read-only and fingerprinted at the start and end of each run | `run_start` log entries |

## Results (actually executed: `bash run_all.sh`, seed 13, 60 iterations)

| | holdout | train |
|---|---:|---:|
| Baseline `v0001` (all tasks return 0) | 0.0069 | 0.1111 |
| Final `v0013` | **0.8542** | 0.8750 |

- There were 67 attempts in total: 60 from the proposer and 7 adversarial submissions. 12 were **accepted** and 55 **rejected**.
  - Accepted: 12 × R4.
  - Rejected: 4 × R1 (invalid), 41 × R2 (per-task regression), 10 × R6 (no gain, or train-only gain).
- Five of the six tasks are now solved exactly on holdout. The evolved `t6` is `(x*(x-y)) + (y*(x-y))`, which is algebraically equal to `(x+y)(x-y)`. `t2_linear` is still partial.
- Each run's `tests.txt` shows 18/18 tests passing. `verify` reports `audit log intact` and `harness files match manifest`.

### The harness improved itself: adaptive proposer (found by its own evaluation)

The first full run used a non-adaptive proposer. The audit log showed **iterations 15–60 all
rejected with R2 on `t2_linear`**: the search kept producing mutants that overfit the train set on that
one task. I made the proposer read the judge's accept/reject history, so it lowers the weight of
tasks with reject streaks, escalates λ, and restarts from random trees. I then measured the change with a
like-for-like ablation (`ablation.py`: same seeds, same 60-iteration budget, isolated state):

| Proposer | seed 1 | seed 2 | seed 3 | mean holdout |
|---|---:|---:|---:|---:|
| non-adaptive | 0.8507 | 0.7674 | 0.6701 | 0.7627 |
| **adaptive** | 0.8507 | 0.8438 | **1.0000** | **0.8981** |

The ablation is deterministic: two separate executions gave identical numbers. Its output is in `results/ablation.json`.

## Artifacts

- `logs/evolution.jsonl`: the hash-chained audit log. Each iteration records the iteration number, timestamp, baseline score, candidate score, train scores, validity or error, decision, rule-based reason, proposer parameters, candidate SHA-256 and archive path.
- `results/evolution_report.md`: table of every attempt. `results/summary.json`: machine-readable summary.
- `results/evolution_run.txt`, `adversarial.txt`, `tamper_demo.txt`, `ablation.{txt,json}`, `tests.txt`, `baseline.json`, `verify.txt`.
- `state/versions/v0001..v0013`: every accepted version, each with `solver.py`, `genome.json` and `eval.json`. `state/candidates/iter_NNNN`: every candidate, including the rejected ones.

## Limitations (honest)

- The proposer is the same process as `tasks.py`, so holdout data is in memory. It is kept out of the
  proposer by code structure (it only reads `TRAIN_INPUTS`), not by isolation. The judge's per-iteration
  decision feeds back into the proposer, which leaks about one bit of holdout information per attempt.
- Anyone with write access can run `lock` again after editing the harness. That event is logged in the audit
  chain, but it is not cryptographically signed.
- `RLIMIT_NPROC` has no effect when running as root. The image runs as the unprivileged `harness` user.
- The benchmark is synthetic, which is deliberate: ground truth is exact and fully machine-verifiable.

## Why this solution deserves to pass

1. **The loop is real, closed and measured.** A baseline is recorded (0.0069) and every candidate gets a fresh, sandboxed, same-procedure evaluation against a re-measured champion. The score rose to 0.8542 through 12 accepted versions, all logged.
2. **The rule is explicit and deterministic, and it is strict about regressions.** It is a pure function with 6 ordered rules. A per-task holdout check rejects net gains that hide a regression, and train-only gains are rejected as overfit. 55 rejections are on record.
3. **Holdout-based judging.** The proposer optimizes train data and the judge decides on disjoint holdout data. That is why a memorizing candidate with a perfect train score is rejected.
4. **Defense in depth against evaluator manipulation.** This means a hash manifest, an AST whitelist, a process sandbox with rlimits, scoring in the parent, nonce-authenticated replies, a hash-chained log and stored-score re-verification. Seven adversarial candidates and a tampered-evaluator copy were all rejected, and you can rerun this with one command.
5. **Rollback and safety.** Versions are immutable, the pointer swap is atomic, a corrupted current version is recovered to the last known good one automatically, and a crashing, hanging or malformed candidate is just a logged REJECT.
6. **The harness improved itself based on evidence.** Its own logs exposed a stuck search. The fix (feedback-adaptive proposer) was validated with a controlled A/B ablation: mean holdout went from 0.763 to 0.898.
7. **Reproducible and tested.** It needs only the standard library, all randomness is seeded, it runs with one command, 18 tests pass, and every number in this README comes from files that `run_all.sh` regenerates.
