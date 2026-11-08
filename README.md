# BrainAid Agent Architect

**Design, audit and harden AI-agent workflows.** A portable Agent Skill for **Claude Code** and **OpenAI Codex**, with offline Python tools for graph linting, static risk discovery and synthetic fault scenarios.

[Русская версия](README_RU.md) · [BrainAid AI News](https://t.me/BrainNeuroassistant) · [Website](https://brainaid.ru)

> **Reliability engineering, not reliability theater.** This skill does **not** guarantee production safety, monitor your services, or test real integrations unless you explicitly arrange project-specific tests. The bundled tools run offline and only inspect files/specs or run disposable synthetic simulations.

## What it does

| Mode | Task | Output |
|---|---|---|
| **DESIGN** | Turn requirements into an executable agent workflow plan | Mermaid, typed state, nodes/edges, budgets, failure handling, human approvals, test plan |
| **AUDIT** | Review an existing repository **without changing it** | Source-linked findings, confidence levels, likely failure paths, prioritized fixes |
| **HARDEN** | Patch verified problems **when explicitly requested** | Minimal changes, reproducible test results, residual risk and rollback notes |

Covers chains/DAGs/cyclic state graphs; bounded generation; API retries vs. business revisions; hybrid validation (code + sourced facts + LLM judgement); checkpoints; version-bound HITL; concurrency; idempotency and reconciliation of uncertain external effects; prompt-injection boundaries; logging and budgets.

**Not another orchestration framework:** this package teaches coding agents to architect and review systems. It does not replace LangGraph, CrewAI, AutoGen, n8n, a database or a real test environment.

## Install (Python 3.10+ for optional tools)

Download the repository as ZIP or clone it. Open a terminal in the folder containing `SKILL.md`.

Install for your user account in **both** Claude Code and Codex:

```bash
python install_skill.py --target both --scope user
```

Or install in the current project (recommended for team projects):

```bash
python install_skill.py --target both --scope project --project /path/to/your/project
```

Windows PowerShell example (from the extracted skill directory):

```powershell
py -3 install_skill.py --target both --scope user
```

The installer **never overwrites** an existing same-named skill without `--force`. An explicit `--force` update keeps the previous installation in a timestamped backup directory. Preview with `--dry-run`.

Skill locations:

- Claude Code: `~/.claude/skills/brainaid-agent-architect/` or `<project>/.claude/skills/brainaid-agent-architect/`
- Codex: `~/.agents/skills/brainaid-agent-architect/` or `<project>/.agents/skills/brainaid-agent-architect/`

Restart the active coding-agent session if the skill is not discovered. Codex can refer to it as `$brainaid-agent-architect`; Claude Code normally as `/brainaid-agent-architect`. Natural language prompting also works.

## First use

**AUDIT (read-only):**

```text
Use brainaid-agent-architect in AUDIT mode. Inspect the current project for
unbounded loops, loss of state, ambiguous API retries, repeated side effects
and insecure human approval. Do not change files. Cite path:line evidence,
separate confirmed findings from hypotheses, and suggest reproducible tests.
```

**DESIGN:**

```text
Use brainaid-agent-architect in DESIGN mode. Design a Telegram support agent
that reads a knowledge base, routes refund disputes to a human and never
creates duplicate CRM tickets. Give me typed state, Mermaid, guards, retries,
HITL and a fault test plan; don't implement yet.
```

**HARDEN:**

```text
Use brainaid-agent-architect in HARDEN mode. Fix the confirmed duplicate
webhook bug from the audit, add focused tests, run only safe local tests
and report exact commands/results. Don't deploy or touch production.
```

## Offline tools

From the repository root:

```bash
python scripts/doctor.py
python scripts/validate_spec.py examples/content_pipeline.json
python scripts/audit_project.py fixtures --format markdown
python scripts/fault_lab.py --all
python -m unittest discover -s tests -v
```

| Tool | What it verifies | What it **does not** verify |
|---|---|---|
| `doctor.py` | Package completeness, metadata and Python version | Agent host discovery / account settings |
| `validate_spec.py` | JSON graph structure, reachability, cycles and declared guards | Runtime termination, real APIs, state storage |
| `audit_project.py` | Heuristic Python AST indicators with source locations | Complete security assessment, JavaScript or dynamic/imported graphs |
| `fault_lab.py` | 12 reproducible **offline mock** scenarios with SQLite | Actual reliability of the target repository or external systems |

The tools use only the Python standard library; no API keys, model calls, dependencies or network required. Static auditing does not execute your project. The offline fault lab creates temporary files outside the audited project and cleans them up.

See [limitations and safe testing](references/testing.md) and [security policy](SECURITY.md).

## Failure scenarios demonstrated by the offline lab

Malformed JSON; API rate limit counted separately from content revision; generation and total-step limits; checkpoint reopen; lost acknowledgement; duplicate webhook; no-progress escalation; stale approval; optimistic concurrency; budget preflight; and ambiguous publishing without automatic retry.

**Passing these tests means the included synthetic demonstration behaves as intended, not that your production agent is safe.** Real integrations require independently designed tests with authorization and a controlled test environment.

## Repository layout

```text
SKILL.md                   Skill instructions (Claude Code + Codex)
install_skill.py           Safe installer, supports dry-run and backups
scripts/                   AST audit, graph linter, fault lab, doctor
references/                Patterns, state, reliability and audit playbooks
templates/                 Design and audit report templates
examples/                  Valid/invalid JSON graph examples
fixtures/                  Intentionally unsafe synthetic Python sample
tests/                     Standard-library unit tests
.github/workflows/         CI (Linux and Windows)
```

## Contributions, license and attribution

Contributions and reproducible bug reports are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Responsible security disclosure: [SECURITY.md](SECURITY.md). Released under the [MIT License](LICENSE).

Developed for [BrainAid AI News](https://t.me/BrainNeuroassistant). The named patterns describe combinations of known engineering techniques; they are not claims of inventing underlying frameworks.
