# Evidence-based audit playbook

## Priority grading

- P0: duplicate money movement/publication, unsafe privilege crossing, unstoppable execution with significant side effect.
- P1: state loss, no global budget, retry/revision confusion, invalid approval version, unsafe concurrency.
- P2: quality drift, uncalibrated judge, missing instrumentation, unbounded costs on low-risk nonproduction tasks.

Assign severity based on actual reachability, privileges, and impact; never based on keywords alone.

## Evidence labels

- **SOURCE-OBSERVED**: concrete file:line and code behavior, but not executed.
- **TEST-CONFIRMED**: reproducible test command, setup, exit code, before/after evidence.
- **HYPOTHESIS**: plausible failure, missing integration context.
- **NOT-ASSESSED**: inaccessible or out of scope. Absence of observed checkpoint calls is not proof checkpoints do not exist.

## Inspection strategy

1. Record current branch/commit when permitted, and scope of inspected files. Skip generated directories and secrets.
2. Build a call graph from entrypoints -> LLM -> tool -> external side effect.
3. Identify all conditional edges, potential cycles, recursive calls and schedule/queue re-drives.
4. Inspect scopes of counters and if they reset when a node reenters or job restarts.
5. Verify direct runtime guards and global budgets, not only prompts that request "no more than three".
6. Verify LLM checks against deterministic tests, fact sources, schema parsing, fallback on invalid response.
7. Look for state checkpoint atomicity, worker concurrency, stale approvals, duplicate webhook handling and transaction boundary.
8. Verify safe handling of ambiguous external API outcome.
9. Propose fault-injection tests only in a local or explicitly permitted sandbox.

## Fast counterexamples

- Router calls `"PASS" in response`: `"NOT PASS"` may incorrectly pass.
- Content loop resets `attempts=0` after selecting a new topic: global loop remains unbounded.
- Publisher sends a post then process dies before storing post ID: replay may duplicate post.
- Waiting approval in RAM only: reboot destroys authority context.
- Two agents overwrite same JSON file: lost update.
- Generated Python runs with production secrets: untrusted code has excessive privileges.
