#!/usr/bin/env python3
"""Offline health check of the installed BrainAid Agent Architect package."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def check_package(root: Path) -> list[dict]:
    checks: list[dict] = []
    def add(name: str, ok: bool, detail: str):
        checks.append({"check": name, "ok": ok, "detail": detail})

    skill = root / "SKILL.md"
    add("skill_file", skill.is_file(), "SKILL.md exists" if skill.is_file() else "Missing SKILL.md")
    if skill.is_file():
        raw = skill.read_text(encoding="utf-8")
        match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
        fields = {}
        if match:
            for line in match.group(1).splitlines():
                if not line.startswith((" ", "\t")) and ":" in line:
                    k, v = line.split(":", 1)
                    fields[k.strip()] = v.strip().strip('"\'')
        add("skill_frontmatter", bool(match and fields.get("name") == root.name and fields.get("description")),
            "name matches directory, description exists" if fields.get("name") == root.name and fields.get("description") else "Invalid frontmatter, name or description")
    required = ["install_skill.py", "scripts/audit_project.py", "scripts/validate_spec.py", "scripts/fault_lab.py",
                "references/patterns.md", "references/testing.md", "tests/test_skill.py", "README.md", "README_RU.md"]
    missing = [path for path in required if not (root / path).is_file()]
    add("package_files", not missing, "Required files present" if not missing else "Missing: " + ", ".join(missing))
    add("python_version", sys.version_info >= (3, 10), "Requires Python 3.10+")
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = check_package(args.root)
    if args.json:
        print(json.dumps({"checks": results}, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{'PASS' if r['ok'] else 'FAIL'} {r['check']}: {r['detail']}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
