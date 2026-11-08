#!/usr/bin/env python3
"""Install this portable skill for Claude Code and/or Codex (Python 3.10+).

Default is project scope; existing installs are never replaced without --force.
--force keeps a timestamped backup and installs via staged directory rename.
"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

TARGET_PATHS = {"claude": Path(".claude") / "skills", "codex": Path(".agents") / "skills"}
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".pytest_cache", ".DS_Store", "*.sqlite", ".coverage")


def install(source: Path, destination: Path, *, force: bool = False, dry_run: bool = False) -> Path | None:
    """Copy using staging; do not follow existing destination symlinks.

    Returns backup directory path when replacing an existing installation.
    """
    source = source.resolve()
    destination = destination.expanduser().absolute()
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError(f"Invalid skill source: {source}")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError(f"Refusing nested/self-copy: {destination}")
    if destination.is_symlink():
        raise ValueError(f"Refusing symlink destination: {destination}")
    if destination.exists() and not force:
        raise FileExistsError(f"{destination} already exists; use --force to replace with backup")
    if dry_run:
        print(f"DRY RUN: {source} -> {destination}" + (" (backup existing)" if destination.exists() else ""))
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    # mkdtemp itself is a directory; remove it before copytree.
    stage.rmdir()
    backup = None
    try:
        shutil.copytree(source, stage, ignore=IGNORED)
        if destination.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = destination.with_name(f"{destination.name}.backup-{stamp}")
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        return backup
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("claude", "codex", "both"), default="both")
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Replace old skill after keeping timestamped backup")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parent
    if source.name != "brainaid-agent-architect":
        parser.error("Source directory must be named brainaid-agent-architect")
    root = Path.home() if args.scope == "user" else args.project.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"Target root does not exist: {root}")
    selected = TARGET_PATHS if args.target == "both" else {args.target: TARGET_PATHS[args.target]}
    dests = [(key, root / relative / source.name) for key, relative in selected.items()]
    # Preflight all targets before changing any.
    for _, dest in dests:
        if dest.is_symlink():
            parser.error(f"Refusing symlink destination: {dest}")
        if dest.exists() and not args.force:
            parser.error(f"{dest} already exists; use --force to replace with backup")
        if source == dest or source in dest.parents or dest in source.parents:
            parser.error(f"Unsafe target: {dest}")
    for target, dest in dests:
        try:
            backup = install(source, dest, force=args.force, dry_run=args.dry_run)
        except (OSError, ValueError, FileExistsError) as exc:
            parser.exit(2, f"Installation failed for {target}: {exc}\n")
        print(f"{target}: {dest}" + (f" (backup: {backup})" if backup else ""))
    print("Dry run only; no changes." if args.dry_run else "Installed. Open a new Claude Code / Codex session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
