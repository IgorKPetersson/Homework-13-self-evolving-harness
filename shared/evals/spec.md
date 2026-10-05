# Evaluation Specification

Both solutions are evaluated using the same criteria.

## 1. Baseline

The harness must measure its current version before evolution begins.

The baseline result must be recorded.

## 2. Candidate Generation

The harness must be able to create or accept a candidate change.

The candidate must be evaluated separately from the current accepted version.

## 3. Evaluation

The baseline and candidate must be evaluated using the same evaluation procedure.

Evaluation results must be machine-verifiable.

## 4. Selection

The harness must use an explicit and deterministic accept/reject rule.

A candidate may only replace the current version if it satisfies the defined acceptance rule.

## 5. Regression Protection

A candidate that performs worse than the current accepted version must not replace it.

The last known good version must remain available.

## 6. Audit Log

Each evolution attempt must log at least:

- iteration number
- baseline score
- candidate score
- decision
- reason for the decision
- timestamp

## 7. Reproducibility

The solution must be runnable from a clean Docker build without manual source-code changes.

The README must contain the commands required to build and run the solution.

## 8. Evaluation Integrity

The harness must not improve its score by modifying, deleting, disabling, or bypassing the shared evaluator.

Files under `/workspace/shared` are treated as read-only challenge infrastructure.

## 9. Failure Handling

A malformed, crashing, or otherwise invalid candidate must not destroy the last known good version.

The harness must handle candidate failure as a rejected evolution attempt.

## 10. Demonstrated Evolution

The final submission must include evidence from at least one real evolution attempt.

The evidence must show a baseline, a candidate, an evaluation result, and an accept or reject decision.

## 11. Final Comparison Areas

The two solutions may be compared on:

- demonstrated self-improvement
- quality of the evaluation system
- robustness
- rollback and safety
- reproducibility
- transparency and auditability
- resistance to evaluator manipulation
- code quality
- architecture
- clarity of documentation

## Interpretation

A harness that only rewrites its own code is not sufficient.

The important behavior is the closed loop:

`measure -> propose -> evaluate -> compare -> accept/reject -> record`