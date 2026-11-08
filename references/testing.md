# Testing strategy and fault-lab boundaries

Bundled tests do **not** execute the audited project. The fault lab validates reference patterns in a synthetic SQLite model.

## Test matrix

| Scenario | Invariant |
|---|---|
| malformed LLM JSON | fail closed, no publish |
| API returns 429 | technical retry, not revision |
| repeated invalid content | controlled exit after max generations |
| process restarts | persistent saved state restored |
| publish success but response lost | reconcile by operation key; no second effect |
| duplicate webhook | same idempotency key; one effect |
| no quality progress | bounded termination/escalation |
| global step exhaustion | stop exactly at configured maximum |
| approval of stale artifact | modified version blocked from publishing |

## Validation layers

1. Static scan: advisory only, no dynamic execution.
2. Schema validation: checks design data, not deployed runtime.
3. Unit tests: executable policies/reducers against mocks.
4. Fault injection: scoped integration test in sandbox.
5. Staging: permitted real API test with fake data, restricted credentials and quotas.
6. Production: monitor and abort/rollback signals, no destructive experiments without approval.

## How to report

Include exact command and pass/fail. If a test case applies only to the simulator, label it `SIMULATION PASS` and **not** `PRODUCTION SAFE`. Explicitly call out unknown, skipped and out-of-scope requirements.
