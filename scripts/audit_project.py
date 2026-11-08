#!/usr/bin/env python3
"""Non-executing Python AST audit of potential AI-graph risks (heuristic, read-only)."""
import argparse
import ast
import json
import os
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".next", "site-packages", ".mypy_cache", ".pytest_cache"}
MAX_BYTES = 512 * 1024
MAX_FILES = 2000
EFFECT_NAMES = {"send_message", "send_email", "publish", "publish_post", "charge", "create_payment", "transfer", "delete_message", "update_crm"}
GUARD_TERMS = ("max_iterations", "max_attempts", "max_steps", "max_total_steps", "recursion_limit", "deadline", "max_cost", "max_llm_calls")
CHECKPOINT_TERMS = ("checkpointer", "SqliteSaver", "PostgresSaver", "MemorySaver", "AsyncSqliteSaver")
IDEMPOTENCY_TERMS = ("idempotency_key", "operation_id", "dedup", "deduplicate")


def constant_name(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in {"START", "END"}:
        return node.id
    return None


def iter_files(root):
    if root.is_file():
        if root.suffix == ".py" and not root.is_symlink():
            yield root
        return
    count = 0
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(base) / d).is_symlink())
        for name in sorted(names):
            path = Path(base) / name
            if path.suffix != ".py" or path.is_symlink():
                continue
            count += 1
            if count > MAX_FILES:
                return
            yield path


def audit(root):
    root = Path(root)
    if not root.exists() or (not root.is_dir() and not root.is_file()):
        raise ValueError(f"Path does not exist: {root}")
    findings, graph_edges = [], []
    scanned, parse_errors, has_guards, has_checkpoints, has_idempotency = 0, 0, False, False, False
    dynamic_edges = False

    def report(severity, code, path, line, message, confidence="advisory"):
        findings.append({"severity": severity, "code": code, "path": str(path), "line": line, "confidence": confidence, "message": message})

    for path in iter_files(root):
        try:
            if path.stat().st_size > MAX_BYTES:
                report("INFO", "SKIPPED_LARGE", path, 0, "Skipped file larger than 512 KiB")
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            report("INFO", "SKIPPED_UNREADABLE", path, 0, str(exc))
            continue
        scanned += 1
        has_guards |= any(t in text for t in GUARD_TERMS)
        has_checkpoints |= any(t in text for t in CHECKPOINT_TERMS)
        has_idempotency |= any(t in text.lower() for t in IDEMPOTENCY_TERMS)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            parse_errors += 1
            report("WARNING", "PARSE_ERROR", path, exc.lineno or 0, f"Python syntax error: {exc.msg}", "source-observed")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
                # break inside a nested function/loop may be misleading; advisory only.
                breaks = any(isinstance(child, ast.Break) for child in ast.walk(node))
                if not breaks:
                    report("HIGH", "WHILE_TRUE", path, node.lineno, "while True with no syntactic break; examine cancellation, time/budget bounds", "source-observed")
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method = node.func.attr
            if method == "add_edge" and len(node.args) >= 2:
                a, b = constant_name(node.args[0]), constant_name(node.args[1])
                if a is not None and b is not None:
                    graph_edges.append((a, b, str(path), node.lineno))
                else:
                    dynamic_edges = True
            if method == "add_conditional_edges":
                dynamic_edges = True
                for arg in node.args[2:3]:
                    if isinstance(arg, ast.Dict):
                        for to_node in arg.values:
                            if constant_name(to_node) is None:
                                report("INFO", "DYNAMIC_ROUTE", path, node.lineno, "Conditional edge target is computed at runtime")
                report("INFO", "CONDITIONAL_EDGES", path, node.lineno, "Conditional routing found: inspect guards and accepted statuses")
            if method in EFFECT_NAMES:
                report("REVIEW", "EXTERNAL_EFFECT", path, node.lineno, f"Possible external side effect: {method}(); review dedup/approval/reconciliation")

    adjacency = defaultdict(set)
    for a, b, _, _ in graph_edges:
        adjacency[a].add(b)
    cycles = set()
    visited, active = set(), []

    def visit(v):
        visited.add(v)
        active.append(v)
        for w in adjacency[v]:
            if w in active:
                seq = active[active.index(w):]
                cycles.add(tuple(sorted(seq)))
            elif w not in visited:
                visit(w)
        active.pop()

    for node in list(adjacency):
        if node not in visited:
            visit(node)
    if cycles:
        first_path, first_line = graph_edges[0][2:4]
        report("REVIEW", "GRAPH_CYCLE", first_path, first_line,
               f"Static add_edge graph contains cycle(s): {sorted(cycles)}. Confirm both local and global termination.")
    if scanned > 0 and (cycles or dynamic_edges) and not has_guards:
        report("REVIEW", "GUARDS_NOT_SEEN", root, 0, "Common budget/iteration guard terms not found in scanned Python files; this is NOT proof guards are absent")
    if scanned > 0 and (cycles or dynamic_edges) and not has_checkpoints:
        report("REVIEW", "CHECKPOINT_NOT_SEEN", root, 0, "No typical checkpointer names detected; verify whether workflow requires persistence elsewhere")
    if any(x["code"] == "EXTERNAL_EFFECT" for x in findings) and not has_idempotency:
        report("REVIEW", "IDEMPOTENCY_NOT_SEEN", root, 0, "Possible external actions without common dedup terms; inspect actual operation ledger and API guarantees")

    return {"scope": str(root), "language": "Python AST", "scanned_files": scanned, "parse_errors": parse_errors,
            "static_add_edge_count": len(graph_edges), "dynamic_routes_seen": dynamic_edges,
            "scope_note": "Read-only heuristics only. Not a security proof or executed runtime audit. May miss generated, dynamic, imported or non-Python behavior.",
            "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, help="Optional report path; otherwise stdout")
    args = parser.parse_args()
    try:
        result = audit(args.path)
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
    if args.format == "json":
        report = json.dumps(result, indent=2, ensure_ascii=False)
    else:
        lines = ["# Static agent audit (advisory)", "", f"Scope: `{result['scope']}`", f"Files inspected: {result['scanned_files']}", "", result["scope_note"], "", "| Severity | Code | Location | Finding |", "|---|---|---|---|"]
        for f in result["findings"]:
            location = f"{f['path']}:{f['line']}"
            msg = f["message"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {f['severity']} | {f['code']} | `{location}` | {msg} |")
        if not result["findings"]:
            lines.append("| INFO | NO_HEURISTIC_FINDINGS | — | No heuristically flagged patterns; NOT proof of safety |")
        report = "\n".join(lines)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"Wrote report: {args.output}")
    else:
        print(report)
    return 0  # findings are advisory; not a CI security verdict


if __name__ == "__main__":
    raise SystemExit(main())
