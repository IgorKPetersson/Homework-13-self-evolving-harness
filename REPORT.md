# Homework 13 — Self-Evolving Harness Challenge

## Objective

The goal of this homework was to compare two AI systems under equal conditions and see which one could create the strongest self-evolving harness.

I gave OpenAI Codex and Claude Code the same task, the same Docker environment, the same resource limits, and the same token budget of 60,000 tokens.

Both systems had to work independently inside separate Docker containers:

- OpenAI: `hw13-openai`
- Claude: `hw13-claude`

Both containers received the same read-only challenge specification under `/workspace/shared`.

Neither model was allowed to access the other model's workspace.

The important requirement was not simply to generate or rewrite code. A successful harness had to create a measurable feedback loop:

`measure -> propose -> evaluate -> compare -> accept/reject -> record`

A candidate should only replace the current version if measurable evaluation results justified the change.

---

## Models use
- OpenAI: GPT-6 Sol Medium
- Claude: Opus 5.5 Medium


---

## Experimental setup

Both competitors started from the same Python 3.12 Docker base environment with Git, Bash and Curl installed.

Each system had:

- 4 CPU cores
- 4 GB memory
- its own writable workspace
- the same read-only shared challenge files
- 60,000 tokens
- the same initial instructions

The two implementations were allowed to choose their own architecture.

This was intentional because the homework was open-ended. I wanted to compare not only whether they could satisfy the minimum requirements, but also how they interpreted the idea of a self-evolving harness.

---

# OpenAI Codex solution

OpenAI built an audited evolution system for a bin-packing policy.

Instead of evolving arbitrary Python programs, its candidates are restricted data-only policies consisting of approved ordering and placement strategies. This substantially reduces the attack surface because candidates cannot provide executable Python code, evaluator paths or score overrides.

The harness uses separate training, validation and holdout datasets.

Its loop is:

1. measure the current baseline,
2. generate candidate policies,
3. screen candidates on training data,
4. evaluate the best candidate on a separate validation gate,
5. accept only a strict improvement with no regression in any case family,
6. atomically switch the active version,
7. retain immutable accepted versions and record the decision in a hash-chained audit log.

The final holdout evaluation is performed after evolution.

### OpenAI results

| Split | Baseline excess bins | Final excess bins |
|---|---:|---:|
| Training | 55 | 11 |
| Validation | 55 | 13 |
| Holdout | 35 | 9 |

The improvement is substantial on all three splits. :chatgpt-content-reference{index="0"}

An especially useful result occurred in the second autonomous round. The candidate improved the training score from 11 to 10 excess bins, but validation did not improve. The harness correctly rejected it and kept the previous version. :chatgpt-content-reference{index="1"}

The solution also demonstrated:

- malformed-candidate rejection,
- immutable accepted versions,
- atomic state changes,
- recovery after interrupted commits,
- trusted-source hashes,
- hash-chained audit logging,
- clean Docker reproduction,
- independent checking of the exact optimization oracle.

The tests explicitly verify that an interrupted commit preserves the last known good state. :chatgpt-content-reference{index="2"}

### Main strength

The strongest part of the OpenAI approach is its simplicity and security model.

By evolving a constrained data representation instead of arbitrary executable code, it avoids many classes of self-modification attacks entirely.

---

# Claude Code solution

Claude chose a more aggressive approach.

Its harness evolves actual solver programs for six integer program-synthesis tasks using genetic programming.

Candidates are evaluated by a sandboxed judge. The proposer searches using training cases, while acceptance is determined using disjoint holdout cases.

The selection system contains six deterministic rules that reject invalid candidates, regressions, overfitting and candidates with no measurable gain. :chatgpt-content-reference{index="3"}

The system also stores immutable accepted versions and uses an atomic pointer to select the current version.

### Claude results

The initial solver had:

- train score: `0.111111`
- holdout score: `0.006945`

:chatgpt-content-reference{index="4"}

After evolution, the final version reached:

- train score: `0.875`
- holdout score: `0.854167`

Five of the six tasks were solved perfectly on the holdout set. :chatgpt-content-reference{index="5"}

Across the complete experiment there were:

- 67 candidate attempts,
- 12 accepted candidates,
- 55 rejected candidates,
- 4 invalid candidates rejected before promotion.

:chatgpt-content-reference{index="6"}

The audit log shows the actual sequence of improvements and rejections rather than only a final score. :chatgpt-content-reference{index="7"}

---

## Adversarial testing

Claude also tested the harness against seven deliberately hostile candidates.

These included:

- syntax errors,
- an infinite loop,
- an attempt to modify the evaluator,
- a sandbox escape attempt,
- a runtime failure,
- invalid return types,
- a solver that memorized training cases.

All seven were rejected. :chatgpt-content-reference{index="8"}

The memorization attack is particularly useful because it demonstrates why the train/holdout separation matters. A candidate can appear successful on training data while still failing to generalize.

The complete test suite contains 18 unit and integration tests covering evaluator attacks, timeouts, rollback, audit integrity, corrupted versions, deterministic selection and evaluator tampering. All 18 passed. :chatgpt-content-reference{index="9"}

A deliberate modification of `selection.py` was also detected by the integrity checker:

`FAIL harness files modified: ['selection.py']`

:chatgpt-content-reference{index="10"}

The unmodified system subsequently verified successfully:

- audit log intact
- harness files match manifest

:chatgpt-content-reference{index="11"}

---

# Self-improvement of the harness itself

The most interesting difference between the two solutions appeared at the meta level.

During Claude's first experiment, the evolution process became stuck repeatedly generating candidates that regressed on the same task.

The proposer was then changed to use its previous accept/reject history:

- tasks with repeated rejection received lower search focus,
- search effort increased,
- repeated failure could trigger a fresh restart.

This change was evaluated in a controlled ablation experiment.

Both proposer versions received the same three random seeds and the same 60-iteration budget.

| Proposer | Mean holdout score |
|---|---:|
| Non-adaptive | 0.762732 |
| Adaptive | **0.898148** |

:chatgpt-content-reference{index="12"} :chatgpt-content-reference{index="13"}

For one of the three seeds, the adaptive version reached a perfect holdout score of `1.0`.

This was the strongest demonstration of self-evolution in the experiment because feedback from previous evaluations was used to improve the process that generates future candidates.

---

# Comparison

Both systems successfully implemented the required closed feedback loop.

OpenAI produced the cleaner and easier-to-reason-about security model. Restricting evolution to data-only policies makes candidate behavior easier to validate and reduces the need for complicated sandboxing.

Claude accepted a larger attack surface by evolving actual Python programs, but compensated with substantially more defensive infrastructure:

- AST validation,
- process isolation,
- CPU and memory limits,
- parent-side scoring,
- authenticated sandbox responses,
- evaluator integrity hashes,
- rollback,
- audit chaining,
- adversarial testing.

Claude also demonstrated a longer evolutionary history and an evidence-based improvement of the search process itself.

For this particular open-ended challenge, I therefore consider **Claude Code the stronger self-evolving harness**.

That does not mean OpenAI failed. Its solution is arguably simpler, more conservative and easier to secure. The comparison shows that "best" depends partly on whether simplicity and reduced attack surface are valued more highly than evolutionary capability and experimentation.

---

# Limitations

The experiment also revealed limitations.

Claude's proposer and holdout data exist in the same process. Although the proposer does not directly read the holdout cases, accept/reject decisions provide indirect information about holdout performance. Claude estimates this as roughly one bit of leakage per attempt. :chatgpt-content-reference{index="14"}

Its integrity mechanism also cannot protect against an attacker who has full write access and deliberately modifies the harness and then re-pins all hashes.

OpenAI's constrained policy representation is safer, but it also limits the space in which the system can evolve. Its demonstrated evolution consists of substantially fewer accepted improvements than Claude's multi-generation program evolution.

The two final numeric scores cannot be compared directly because the systems evolved solutions to different benchmark problems. The comparison therefore focuses on architecture, demonstrated evolution, robustness, evaluation quality and reproducibility rather than comparing their raw scores.

---

# Why I think I deserve to pass

I believe this homework deserves a pass because I did more than run two AI models and compare their final answers.

I created a controlled experiment in which both systems received:

- the same Docker starting environment,
- the same resource limits,
- the same task specification,
- the same token budget,
- isolated writable workspaces,
- the same read-only challenge infrastructure.

Both systems then produced real executable harnesses and generated machine-verifiable evidence.

The experiment demonstrates the full self-evolution loop in practice:

`measure -> propose -> evaluate -> compare -> accept/reject -> record`

It includes successful improvements, rejected regressions, malformed candidates, rollback mechanisms, integrity checks, reproducible runs and adversarial tests.

Most importantly, the experiment produced an unexpected result that could actually be measured: one harness used evidence from its own failed search history to improve its future candidate-generation strategy, and a controlled three-seed ablation showed that the adaptive version improved mean holdout performance from approximately `0.763` to `0.898`.

I can therefore explain not only **what the systems built**, but also **how I tested whether their claims were true, what their weaknesses are, and why I consider one approach stronger than the other**.

For an open-ended homework about self-evolving harnesses, I think that combination of controlled setup, executable evidence, critical comparison and documented limitations demonstrates the intended learning outcome.