# Homework 13: audited self-evolving harness

This project evolves a **data-only bin-packing policy**. A policy is a bounded portfolio of ordering and placement strategies. The trusted harness generates candidate policies, measures them against exactly solvable packing cases, and atomically switches the active content-addressed version only when a separate validation gate improves. A candidate cannot supply Python, a file path, a score, or an evaluator override.

## Reproduce from a clean Docker build

Run these PowerShell commands at the repository root. The Docker build context is only `openai/`. The reproduction script copies only `harness/*.py` and `tests/*.py` into a new directory **inside `/workspace/openai/reproductions/`**, then runs tests, a new baseline, a rejected probe, autonomous evolution, a final evaluation, and verification. It does not reset the submitted run.

```sh
docker build -t hw13-openai-solution -f openai/Dockerfile openai
$openaiPath = (Resolve-Path openai).Path
$sharedPath = (Resolve-Path shared).Path
docker run --rm --mount "type=bind,source=$openaiPath,target=/workspace/openai" --mount "type=bind,source=$sharedPath,target=/workspace/shared,readonly" -w /workspace/openai hw13-openai-solution python scripts/reproduce.py
```

The command prints the new reproduction directory. Its `results/final.json`, `audit/evolution.jsonl`, `results/demo-output.json` equivalent (`demo.stdout.txt`), and `verify.stdout.txt` are retained. A nonzero test, demo, or verification exit code fails the script. No dependency beyond Python 3.12's standard library is required.

To inspect or continue the submitted run in the assigned container:

```sh
docker exec hw13-openai python -m unittest discover -s tests -v
docker exec hw13-openai python -m harness.cli verify
docker exec hw13-openai python -m harness.cli evolve --rounds 3
docker exec hw13-openai python -m harness.cli finalize
```

`evolve` can make additional attempts. Run `finalize` afterward to update `results/final.json` before `verify`. To submit a JSON policy, place it in `candidates/` and run `python -m harness.cli try candidates/name.json` inside the container.

## How the loop works

1. **Baseline:** `input` order with `first` fit is measured on 72 training and 72 validation cases before generating candidates. The result is saved in `results/baseline.json`.
2. **Propose:** the generator enumerates single-strategy replacements and additions to the current portfolio. Strategies are chosen from four item orders and four placement rules. The portfolio is limited to four unique strategies. Candidates are saved by SHA-256 under `candidates/`.
3. **Screen:** every candidate gets the same training cases and exact optimum. Proposals without a strict training improvement are rejected and logged. The greatest training gain is selected; ties favor proposals that retain all active strategies, then fewer strategies and canonical JSON order. The validation gate is never used for proposal ranking.
4. **Gate:** the selected candidate and active policy run the same 72 validation cases. Acceptance requires strictly fewer **excess bins** (bins used minus exact optimum), identical case digest, and no increase in excess bins for any of the six case families. A tie or family regression is rejected. There is no probabilistic threshold.
5. **Commit:** after acceptance, an immutable policy version is written and the active pointer in `state.json` is replaced atomically. An intent and outcome are recorded in a hash-chained JSONL audit. If a process stops between intent and commit, the next run reconciles the intent against the active pointer. A failure before pointer replacement leaves the previous version active.
6. **Final check:** the 48-case holdout is evaluated only after evolution. `verify` replays the baseline and final scores on all splits, checks the active version digest, the audit chain and its recorded head, and checks the pinned trusted-source manifest.

Cases use six families: uniform, complementary pairs, triples, mixed large and small items, clustered sizes, and small items followed by large ones. Each split has independent deterministic seeds. Every output is checked for missing, duplicated, or overfull bins. The exact optimum is computed by a subset dynamic program and cross-checked against an independent exhaustive search in tests. Fixed seeded cases and a held-out final split make the reported result reproducible; they are not a claim of general optimality on unseen distributions.

## Verified submitted result

The submitted run was executed inside `hw13-openai` and verified after the final malformed-candidate attempt. Scores are lower-is-better excess bins.

| Split | Cases | Baseline bins / optimum | Final bins / optimum | Baseline excess | Final excess |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 72 | 479 / 424 | 435 / 424 | 55 | 11 |
| Validation gate | 72 | 486 / 431 | 444 / 431 | 55 | 13 |
| Holdout | 48 | 326 / 291 | 300 / 291 | 35 | 9 |

The active version is `5b22e0a6e1bd77cf1513126a17d3eea1368b19550256329d0d5f26ac90f2baa4`, containing `input/first` plus `descending/best`.

The real evolution record includes:

- A poor `ascending/next` probe: validation excess 90 versus baseline 55; rejected.
- Autonomous round 1: training excess 55 to 11 and validation excess 55 to 13; accepted.
- Autonomous round 2: training excess 11 to 10 but validation stayed 13; rejected, active version unchanged.
- An invalid JSON policy attempting to add `score_override`: rejected before evaluation, active version unchanged.

`python -m unittest discover -s tests -v` passed all six tests. A separate source-only reproduction under `reproductions/` also passed its tests, demo, and verification and produced validation excess 13 and holdout excess 9.

## Artifacts and integrity

- `harness/`: trusted policy interpreter, case generator, exact oracle, evaluator, storage, evolution engine, and CLI.
- `tests/`: independent oracle, feasibility, schema, gate, and interrupted-commit tests.
- `results/baseline.json`, `results/round-*.json`, `results/attempt-*.json`, `results/final.json`: machine-readable evidence.
- `audit/evolution.jsonl`: timestamped hash-chained records for screening, decisions, commit intents, and commits. `audit/trusted-manifest.json` pins trusted source and the read-only shared task and spec for the entire run.
- `versions/`: immutable accepted policy snapshots. `state.json` points to the active one.
- `candidates/`: content-addressed generated proposals and the malformed example.
- `experiments/pre-anchor-run/`: an earlier rejected run retained as evidence of the selection improvement made during development.

The candidate language only contains allowlisted strategy names. This prevents candidate code execution and direct score manipulation. The active pointer is never changed for a malformed, crashing, tied, or regressing candidate. The pinned manifest makes a later source or shared-spec change fail closed. The hash chain detects accidental or isolated audit edits; it is not a cryptographic signature against an attacker who can rewrite the entire workspace.

## Why this solution deserves to pass

It demonstrates the complete measured loop, including a real accepted improvement and several real rejections, with an exact independent objective, a held-out comparison, deterministic family-safe selection, recoverable atomic commits, pinned evaluator code, machine-verifiable artifacts, and a clean-copy Docker reproduction.
