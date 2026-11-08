# State, budgets and external effects

## State data contract

Prefer typed structures (dataclass/Pydantic/TypedDict) with versioned migrations. Partition:

- immutable brief: goal, acceptance criteria, authorization scope, policy;
- working state: node, counters, validated decisions, error class;
- artifact store: content/version/checksum/source provenance;
- ledger: external operations and reconciliation status;
- log/trace: structured events with sensitive-data redaction.

Parallel writes require reducer semantics, compare-and-swap revisions or transactional isolation. A Markdown summary can document state but does not replace a database.

## Global and local budgets

Suggested first lab bounds (calibrate before production):

```yaml
max_generations_per_artifact: 3  # including first generation
max_total_steps: 25
max_llm_calls: 12
max_cost_usd: 2.00
deadline_seconds: 300
max_no_progress_rounds: 2
max_api_retries_per_call: 2
```

Enforce budgets in the executable runtime before paid calls. Parallel workers must reserve capacity atomically. Configured limits alone do not guarantee enforcement.

## Technical vs semantic retries

- Technical: 429 (respect Retry-After), transient 5xx, temporary network errors. Bounded exponential backoff plus jitter; authentication failures usually should not retry unchanged.
- Semantic: valid response fails a deterministic or evaluated quality criterion; new artifact revision and independent revision counter.
- Unknown external result: *reconcile before retrying*; do not assume exception means no side effect occurred.

## Durable operation workflow

1. Assign stable `operation_id` / idempotency key from run + action + target/version.
2. Persist intent before attempting external operation.
3. Execute at-least-once only when idempotent API or your dedup/reconciliation layer makes it safe.
4. On ambiguous response, query external platform using operation metadata/status where supported.
5. Persist confirmed external ID and completion state.

If the remote platform cannot query/identify previously performed operations, automatic retry of an ambiguous side effect may be unsafe. Escalate to manual reconciliation.

## Human approval invariant

A valid approval must bind `run_id + actor + role + exact action + artifact hash + expiry`; any change to the artifact invalidates the approval. On resume, verify authorization again if necessary.

## Trust boundaries

Retrieved content can be malicious. Treat it as data only. Avoid broad API credentials for validators, use least privilege, sandbox executable generated code, strip sensitive data from traces, and require explicit confirmation for high-risk effects.
