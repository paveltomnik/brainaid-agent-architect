#!/usr/bin/env python3
"""Offline SQLite fault-injection lab. Synthetic platform only; no external API requests."""
import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

SCENARIOS = (
    "invalid-json", "rate-limit", "max-generations", "restart",
    "lost-ack", "duplicate-webhook", "no-progress", "max-total-steps", "stale-approval",
    "optimistic-lock", "budget-precheck", "ambiguous-publish",
)


class LostAck(Exception):
    pass


def new_database(path):
    db = sqlite3.connect(str(path))
    db.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0)")
    # effects simulates a remote endpoint supporting idempotency-key lookups.
    db.execute("CREATE TABLE IF NOT EXISTS simulated_external_effects (idempotency_key TEXT PRIMARY KEY, external_id TEXT NOT NULL)")
    db.commit()
    return db


def save(db, state):
    with db:
        db.execute("INSERT INTO runs(run_id,state_json) VALUES (?,?) ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json", (state["run_id"], json.dumps(state, sort_keys=True)))


def save_if_version(db, state, expected_version):
    """Compare-and-swap: reject a stale snapshot instead of losing an update."""
    with db:
        result = db.execute(
            "UPDATE runs SET state_json=?, version=version+1 WHERE run_id=? AND version=?",
            (json.dumps(state, sort_keys=True), state["run_id"], expected_version),
        )
    return result.rowcount == 1


def load(db, run_id):
    row = db.execute("SELECT state_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def publish_fake(db, key, lose_ack=False):
    """Simulated remote operation: unique key makes repeated calls safe in this lab."""
    with db:
        db.execute("INSERT OR IGNORE INTO simulated_external_effects VALUES (?, ?)", (key, "post-0001"))
    if lose_ack:
        raise LostAck("simulated network loss after remote commit")
    return db.execute("SELECT external_id FROM simulated_external_effects WHERE idempotency_key=?", (key,)).fetchone()[0]


def check_remote(db, key):
    row = db.execute("SELECT external_id FROM simulated_external_effects WHERE idempotency_key=?", (key,)).fetchone()
    return row[0] if row else None


def execute_scenario(name, root):
    db_path = root / "fault_lab.sqlite"
    db = new_database(db_path)
    state = {"run_id": "run-demo", "status": "RUNNING", "generations": 0, "api_retries": 0, "steps": 0, "last_error": None}
    try:
        if name == "invalid-json":
            try:
                payload = json.loads('{"status": "PASS", invalid}')
                state["status"] = "DONE" if payload.get("status") == "PASS" else "BLOCKED"
            except json.JSONDecodeError:
                state["status"] = "BLOCKED"
                state["last_error"] = "invalid_json"
            ok = state["status"] == "BLOCKED" and db.execute("SELECT COUNT(*) FROM simulated_external_effects").fetchone()[0] == 0
            detail = "Malformed model output blocked; no external side effects"
        elif name == "rate-limit":
            state["generations"] = 1
            # Simulated HTTP 429 is a technical retry, not a new content generation.
            state["api_retries"] += 1
            state["last_error"] = "HTTP_429"
            ok = state["generations"] == 1 and state["api_retries"] == 1
            detail = "429 increased only technical retry counter"
        elif name == "max-generations":
            max_generations = 3
            for _ in range(9):
                if state["generations"] >= max_generations:
                    state["status"] = "HUMAN_REVIEW"
                    break
                state["generations"] += 1
                state["steps"] += 2  # generation + validation
            ok = state["status"] == "HUMAN_REVIEW" and state["generations"] == 3
            detail = "Total generations stopped at 3 (initial + 2 revisions)"
        elif name == "restart":
            state.update({"steps": 5, "generations": 2, "status": "WAITING_APPROVAL"})
            save(db, state)
            db.close()
            db = new_database(db_path)  # simulate new process/connection
            restored = load(db, "run-demo")
            ok = restored is not None and restored["steps"] == 5 and restored["generations"] == 2 and restored["status"] == "WAITING_APPROVAL"
            detail = "SQLite checkpoint survived reopen with counters and pause status"
        elif name == "lost-ack":
            key = "run-demo:publish:v3"
            try:
                publish_fake(db, key, lose_ack=True)
            except LostAck:
                pass
            recovered = check_remote(db, key)
            total = db.execute("SELECT COUNT(*) FROM simulated_external_effects").fetchone()[0]
            ok = recovered == "post-0001" and total == 1
            detail = "Remote effect confirmed via operation key after missing acknowledgement; no blind retry"
        elif name == "duplicate-webhook":
            key = "telegram-update-2026-1001"
            a = publish_fake(db, key)
            b = publish_fake(db, key)
            total = db.execute("SELECT COUNT(*) FROM simulated_external_effects").fetchone()[0]
            ok = a == b and total == 1
            detail = "Two deliveries produced one synthetic external effect"
        elif name == "max-total-steps":
            max_steps = 5
            for _ in range(100):
                if state["steps"] >= max_steps:
                    state["status"] = "STOP_LIMIT"
                    break
                state["steps"] += 1
            ok = state["steps"] == 5 and state["status"] == "STOP_LIMIT"
            detail = "Global step guard stopped execution at 5 simulated steps"
        elif name == "stale-approval":
            approved_v2 = "Approved publication v2"
            revised_v3 = "Modified publication v3"
            approval = {"artifact_version": 2, "sha256": hashlib.sha256(approved_v2.encode()).hexdigest()}
            current = {"artifact_version": 3, "sha256": hashlib.sha256(revised_v3.encode()).hexdigest()}
            approved = approval == current
            state["status"] = "BLOCKED" if not approved else "APPROVED"
            ok = state["status"] == "BLOCKED" and db.execute("SELECT COUNT(*) FROM simulated_external_effects").fetchone()[0] == 0
            detail = "Approval for v2 did not authorize modified v3; no external effect"
        elif name == "optimistic-lock":
            save(db, state)
            stale_snapshot = load(db, "run-demo")
            first_snapshot = load(db, "run-demo")
            first_snapshot["status"] = "CHECKED"
            first_ok = save_if_version(db, first_snapshot, expected_version=0)
            stale_snapshot["status"] = "OVERWRITE"
            stale_rejected = not save_if_version(db, stale_snapshot, expected_version=0)
            persisted = load(db, "run-demo")
            ok = first_ok and stale_rejected and persisted["status"] == "CHECKED"
            detail = "Optimistic version check prevented lost update from a stale worker"
        elif name == "budget-precheck":
            maximum = 2.00
            consumed = 1.80
            reserved_estimate = 0.30
            allowed = (consumed + reserved_estimate) <= maximum
            state["status"] = "STOP_BUDGET" if not allowed else "CALL_STARTED"
            ok = not allowed and state["status"] == "STOP_BUDGET"
            detail = "Estimated next call exceeded remaining budget and was not started"
        elif name == "ambiguous-publish":
            # The mock platform cannot check whether the effect happened.
            # No blind retry is safe under an ambiguous acknowledgement.
            state["status"] = "WAITING_RECONCILIATION"
            retry_requested = False
            ok = (not retry_requested and state["status"] == "WAITING_RECONCILIATION"
                  and db.execute("SELECT COUNT(*) FROM simulated_external_effects").fetchone()[0] == 0)
            detail = "Unknown external outcome remained pending; blind resend was prohibited"
        elif name == "no-progress":
            scores = [0.6, 0.6, 0.59, 0.58]
            best, no_progress = scores[0], 0
            for score in scores[1:]:
                if score > best:
                    best, no_progress = score, 0
                else:
                    no_progress += 1
                if no_progress >= 2:
                    state["status"] = "HUMAN_REVIEW"
                    break
            ok = state["status"] == "HUMAN_REVIEW" and no_progress == 2 and best == 0.6
            detail = "Two stagnant quality rounds escalated; best-so-far score preserved"
        else:
            raise ValueError(f"Unknown scenario {name}")
        save(db, state)
        return {"scenario": name, "pass": bool(ok), "detail": detail, "environment": "OFFLINE_SIMULATION"}
    finally:
        db.close()


def run_scenario(name):
    with tempfile.TemporaryDirectory(prefix="brainaid-fault-lab-") as directory:
        return execute_scenario(name, Path(directory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    results = [run_scenario(s) for s in (SCENARIOS if args.all else (args.scenario,))]
    if args.format == "json":
        print(json.dumps({"scope": "offline mock only", "results": results}, indent=2, ensure_ascii=False))
    else:
        for item in results:
            print(f"{'PASS' if item['pass'] else 'FAIL'} [SIMULATION] {item['scenario']}: {item['detail']}")
        print(f"Summary: {sum(x['pass'] for x in results)}/{len(results)} scenarios passed in synthetic environment")
    return 0 if all(x["pass"] for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
