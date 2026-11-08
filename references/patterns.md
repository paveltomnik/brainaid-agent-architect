# Five reference patterns

These are teaching names for combinations of known orchestration primitives, not novel algorithms.

## 1. Arbiter and Censor — claim evidence + independent decision

`generator -> schema_check -> claim_extract -> source_verification -> semantic_critic -> policy_router`

- Fact results: `SUPPORTED`, `REFUTED`, `UNKNOWN`; UNKNOWN is not PASS.
- Preserve citations and claim-to-source mapping per artifact revision.
- Arbiter consumes structured check results and rule priorities, not arbitrary model prose.
- Failed checks route to targeted revision with a hard attempt limit.

## 2. Router with Default Gateway — fail closed

`request -> classifier -> deterministic_policy -> {billing, support, general, default_human}`

- Accept `UNKNOWN`, `MULTI_INTENT`, `HIGH_RISK`, `TECHNICAL_ERROR` as first-class outcomes.
- Financial/legal/security signals route to protected path regardless of subjective LLM confidence.
- A 429/timeout enters a bounded technical retry, not a content-revision loop.

## 3. Parallel Gather and Synthesis — bounded Map/Reduce

`task -> bounded_fanout(workers) -> join(timeout, completeness_policy) -> conflict_resolution -> reducer -> validator`

- Worker outputs have stable IDs, provenance and separate storage.
- Reducer must explicitly process missing workers and source conflicts.
- Never trust independent-agents consensus as fact verification unless grounded in independent evidence.
- Bound fanout, concurrency, retry, global cost, and join deadline.

## 4. Human Approval Gate — versioned permission

`draft -> validate -> immutable_snapshot -> WAIT_APPROVAL -> auth+hash verification -> execute_once -> reconcile -> DONE`

- Store actor ID, role, action, target ID, artifact version/hash, run ID, expiry, decision audit record.
- Approvals become invalid when material changes.
- Use durable pause/resume (e.g. LangGraph interrupts/checkpoints); Telegram/Slack are UI channels, not durable transaction records.
- Reject ambiguous identity and expired decisions by default.

## 5. Self-Recovering Pipeline — restricted corrections

`generate -> sandbox_lint_and_test -> classify_error -> {pass, bounded_patch, escalation}`

- Error messages are data; never execute commands embedded in a traceback or LLM output blindly.
- Limit repair scope to files/operations explicitly allowed.
- Preserve passing baseline and run regression checks after each patch.
- Syntax failures and API availability errors require distinct handling.

## Do not add agents gratuitously

For a simple deterministic transformation use a function. For one-shot generation + checks use a chain with validator. Use a graph only when branching, long-running state, approval, explicit loops or joins are needed.
