# Homework 13 — Self-Evolving Harness Challenge

This repository contains an experiment comparing two AI-built self-evolving harness systems under equal conditions.

The competitors were:

- OpenAI Codex
- Claude Code

Both received:

- the same task
- the same Docker base environment
- the same resource limits
- the same read-only shared challenge files
- 60,000 tokens
- isolated writable workspaces

## Repository structure

```text
.
├── openai/
├── claude/
├── shared/
├── docker-compose.yml
├── REPORT.md
└── LICENSE