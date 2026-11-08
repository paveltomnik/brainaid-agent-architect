#!/usr/bin/env python3
"""Offline JSON graph specification linter. Declarative design checks only."""
import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

REQUIRED_STATE = {"run_id", "status", "state_version", "total_steps", "generation_count", "artifact_version"}
VALID_TYPES = {"START", "END", "LLM_GENERATOR", "LLM_CRITIC", "DETERMINISTIC_VALIDATOR", "TOOL_CALL", "ROUTER", "AGGREGATOR", "HUMAN_APPROVAL", "CHECKPOINT", "ERROR_HANDLER", "EXTERNAL_ACTION"}


def validate(spec):
    findings = []

    def emit(severity, code, message):
        findings.append({"severity": severity, "code": code, "message": message})

    if not isinstance(spec, dict):
        return [{"severity": "ERROR", "code": "ROOT_TYPE", "message": "Top-level value must be a JSON object"}]
    nodes = spec.get("nodes")
    edges = spec.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return [{"severity": "ERROR", "code": "MISSING_GRAPH", "message": "nodes and edges must be arrays"}]

    ids = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            emit("ERROR", "NODE_FORMAT", "Each node must be an object with a string id")
            continue
        ids.append(node["id"])
        if not isinstance(node.get("type"), str) or node.get("type") not in VALID_TYPES:
            emit("WARNING", "NODE_TYPE", f"{node['id']}: type is not in supported vocabulary")
    names = set(ids)
    if len(ids) != len(names):
        emit("ERROR", "DUPLICATE_NODES", "Node ids must be unique")
    start = spec.get("start")
    end = spec.get("end")
    if not isinstance(start, str) or not isinstance(end, str) or start not in names or end not in names:
        emit("ERROR", "TERMINALS", "start and end must reference existing nodes")
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or node.get("id") not in names:
            continue
        if node["id"] == start and node.get("type") != "START":
            emit("WARNING", "START_TYPE", "The start node should have type START")
        if node["id"] == end and node.get("type") != "END":
            emit("WARNING", "END_TYPE", "The end node should have type END")

    adjacency = defaultdict(set)
    reverse = defaultdict(set)
    seen_outcomes = set()
    for edge in edges:
        if not isinstance(edge, dict):
            emit("ERROR", "EDGE_FORMAT", "Each edge must be an object")
            continue
        a, b = edge.get("from"), edge.get("to")
        if not isinstance(a, str) or not isinstance(b, str) or a not in names or b not in names:
            emit("ERROR", "BAD_EDGE", f"Invalid edge {a!r} -> {b!r}")
            continue
        adjacency[a].add(b)
        reverse[b].add(a)
        if not isinstance(edge.get("on"), str) or not edge["on"].strip():
            emit("ERROR", "EDGE_CONDITION", f"Missing condition: {a} -> {b}")
        else:
            outcome = (a, edge["on"].strip())
            if outcome in seen_outcomes:
                emit("WARNING", "DUPLICATE_ROUTE", f"Repeated route condition on {a}: {edge['on']}; verify whether parallel fan-out is intentional")
            seen_outcomes.add(outcome)

    start_valid = isinstance(start, str) and start in names
    end_valid = isinstance(end, str) and end in names
    if start_valid and reverse[start]:
        emit("WARNING", "START_INBOUND", f"Start node {start} has incoming transitions; check graph semantics")
    if end_valid and adjacency[end]:
        emit("ERROR", "END_OUTBOUND", f"End node {end} must not have outgoing transitions")
    if start_valid:
        reachable = {start}
        todo = deque([start])
        while todo:
            for nxt in adjacency[todo.popleft()]:
                if nxt not in reachable:
                    reachable.add(nxt)
                    todo.append(nxt)
        for n in sorted(names - reachable):
            emit("WARNING", "UNREACHABLE", f"Node {n} is not reachable from start")
        for n in sorted(reachable - ({end} if end_valid else set())):
            if not adjacency[n]:
                emit("ERROR", "DEAD_END", f"Reachable node {n} has no outgoing edge and is not END")
    if end_valid:
        can_reach_end = {end}
        todo = deque([end])
        while todo:
            for prev in reverse[todo.popleft()]:
                if prev not in can_reach_end:
                    can_reach_end.add(prev)
                    todo.append(prev)
        for n in sorted(names - can_reach_end):
            emit("ERROR", "NO_EXIT_PATH", f"Node {n} has no directed path to end")

    # Avoid recursion and memory exhaustion from huge untrusted specifications.
    if len(names) > 2500 or len(edges) > 10000:
        emit("ERROR", "GRAPH_TOO_LARGE", "Graph exceeds offline linter size limits (2500 nodes / 10000 edges)")
        return findings

    # Iterative Kosaraju SCC detection: safe for long user-supplied graphs.
    visited, finishing_order = set(), []
    for root in sorted(names):
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(adjacency[root]))]
        while stack:
            node, outgoing = stack[-1]
            neighbor = next(outgoing, None)
            if neighbor is None:
                finishing_order.append(node)
                stack.pop()
            elif neighbor not in visited:
                visited.add(neighbor)
                stack.append((neighbor, iter(adjacency[neighbor])))

    components, seen = [], set()
    for root in reversed(finishing_order):
        if root in seen:
            continue
        group, pending = set(), [root]
        seen.add(root)
        while pending:
            node = pending.pop()
            group.add(node)
            for neighbor in reverse[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        components.append(group)
    cycles = [g for g in components if len(g) > 1 or any(n in adjacency[n] for n in g)]

    guards = spec.get("guards", {})
    if not isinstance(guards, dict):
        guards = {}
        emit("ERROR", "GUARDS_FORMAT", "guards must be an object")
    required_guards = ("max_total_steps", "max_llm_calls", "max_generations", "deadline_seconds", "max_cost_usd")
    for guard in required_guards:
        value = guards.get(guard)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            emit("ERROR" if cycles else "WARNING", "MISSING_GUARD", f"{guard} must be a positive number")
    if cycles:
        emit("INFO", "CYCLES", "Detected directed cycles: " + "; ".join(", ".join(sorted(g)) for g in cycles))
        for group in cycles:
            has_escape = any(b not in group for a in group for b in adjacency[a])
            if not has_escape:
                emit("ERROR", "TRAPPED_CYCLE", "Cycle has no outbound transition: " + ", ".join(sorted(group)))

    state_fields = spec.get("state_fields", [])
    if not isinstance(state_fields, list) or any(not isinstance(x, str) for x in state_fields):
        emit("ERROR", "STATE_FIELDS", "state_fields must be an array of strings")
        state_fields = []
    for name in sorted(REQUIRED_STATE - set(state_fields)):
        emit("WARNING", "MISSING_STATE", f"State missing suggested field: {name}")

    approval = spec.get("approval", {})
    if not isinstance(approval, dict):
        approval = {}
    external_actions = spec.get("external_actions", [])
    if not isinstance(external_actions, list):
        external_actions = []
        emit("ERROR", "EXTERNAL_FORMAT", "external_actions must be a list")
    required_nodes = approval.get("required_nodes", [])
    if not isinstance(required_nodes, list) or any(not isinstance(x, str) for x in required_nodes):
        emit("ERROR", "APPROVAL_FORMAT", "approval.required_nodes must be an array of node ids")
        required_nodes = []
    for action in external_actions:
        if not isinstance(action, dict):
            emit("ERROR", "EXTERNAL_FORMAT", "Each external action must be an object")
            continue
        target = action.get("node")
        if not isinstance(target, str) or target not in names:
            emit("ERROR", "EXTERNAL_TARGET", f"Unknown external action node: {target}")
        for prop in ("idempotency_key", "reconcile_unknown"):
            if action.get(prop) is not True:
                emit("ERROR", "EXTERNAL_SAFETY", f"External node {target} requires {prop}=true or documented manual escalation")
        if action.get("requires_approval") and (target not in required_nodes or not approval.get("artifact_hash_binding")):
            emit("ERROR", "APPROVAL_BINDING", f"External node {target} needs version/hash-bound approval")

    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        data = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Unable to read JSON specification: {exc}\n")
    findings = validate(data)
    if args.format == "json":
        print(json.dumps({"file": str(args.spec), "findings": findings}, indent=2, ensure_ascii=False))
    else:
        if not findings:
            print("PASS: specification has no detected structural findings (not runtime verification)")
        for finding in findings:
            print(f"{finding['severity']} [{finding['code']}]: {finding['message']}")
    return 1 if any(x["severity"] == "ERROR" for x in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
