# Homework 13 — Self-Evolving Harness Challenge

## Task

Build a self-evolving harness system inside your assigned Docker container.

The system must be able to:

1. evaluate its current solution,
2. propose or create an improved candidate,
3. test the candidate,
4. compare the candidate against the current version,
5. keep the candidate only if evaluation results improve,
6. reject or roll back regressions,
7. log what happened.

## Equal conditions

Both OpenAI and Claude receive:

- 60,000 tokens
- the same task
- the same Docker starting environment
- the same resource limits
- the same shared evaluation specification
- no access to the other model's implementation

OpenAI may only modify files inside `/workspace/openai`.

Claude may only modify files inside `/workspace/claude`.

Files under `/workspace/shared` are read-only during the challenge.

## Minimum requirements

The harness must:

- use machine-verifiable evaluations
- measure a baseline before evolution starts
- create or accept at least one candidate improvement
- evaluate the candidate
- compare candidate and baseline
- use an explicit accept/reject rule
- reject regressions
- log iterations and results
- be reproducible
- protect the evaluator from trivial manipulation
- produce a verifiable final result

## Required deliverables

Each solution must include:

- source code
- README with run instructions
- evaluation results
- evolution log
- at least one accepted or rejected candidate example
- a short section titled:

  `Why this solution deserves to pass`

## Important

A system is not considered self-evolving merely because it can rewrite its own code.

It must be able to measure whether a change is actually better and make a reproducible decision based on evaluation results.