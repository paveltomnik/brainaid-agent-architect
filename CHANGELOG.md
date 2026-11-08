# Changelog

## 1.0.0 — 2026-11-09

- First public-ready **portable skill distribution** for Claude Code and Codex: DESIGN, AUDIT and HARDEN modes.
- English and Russian README, MIT license, contribution/security guidance, GitHub Actions matrix (Windows and Linux).
- Safe installer with project/user scopes, dry run and timestamped backups on explicit replacement.
- Python AST audit, JSON graph linter, package doctor, report templates and references.
- Twelve offline synthetic fault scenarios: malformed structured output, API rate limit, bounded generations, checkpoint reopen, missing acknowledgement, duplicate webhook, no-progress, global-step limit, stale approval, optimistic locking, budget preflight and ambiguous external status.
- Expanded unit tests and deterministic fixtures.

**Verification note:** Offline package and simulated scenarios only. No claim of integration testing against real Claude Code/Codex application runtime, LangGraph, Telegram, payment systems or production APIs.

## 0.1.0 — 2026-11-08

- Initial portable skill prototype with nine offline fault simulations and initial static auditing.

### Final package verification

- 11 Python unit tests, including installer safety, large-graph traversal, malformed specifications and package integrity.
- 12 offline simulated failure scenarios. These are **not** live integration tests.
