# Static agent audit (advisory)

Scope: `fixtures`
Files inspected: 1

Read-only heuristics only. Not a security proof or executed runtime audit. May miss generated, dynamic, imported or non-Python behavior.

| Severity | Code | Location | Finding |
|---|---|---|---|
| HIGH | WHILE_TRUE | `fixtures/unsafe_langgraph_demo.py:11` | while True with no syntactic break; examine cancellation, time/budget bounds |
| REVIEW | EXTERNAL_EFFECT | `fixtures/unsafe_langgraph_demo.py:7` | Possible external side effect: publish(); review dedup/approval/reconciliation |
| REVIEW | GRAPH_CYCLE | `fixtures/unsafe_langgraph_demo.py:4` | Static add_edge graph contains cycle(s): [('check', 'draft')]. Confirm both local and global termination. |
| REVIEW | GUARDS_NOT_SEEN | `fixtures:0` | Common budget/iteration guard terms not found in scanned Python files; this is NOT proof guards are absent |
| REVIEW | CHECKPOINT_NOT_SEEN | `fixtures:0` | No typical checkpointer names detected; verify whether workflow requires persistence elsewhere |
| REVIEW | IDEMPOTENCY_NOT_SEEN | `fixtures:0` | Possible external actions without common dedup terms; inspect actual operation ledger and API guarantees |
