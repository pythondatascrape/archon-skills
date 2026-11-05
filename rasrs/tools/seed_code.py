#!/usr/bin/env python3
"""Backfill or refresh memory's links from approved plan rules to code and tests.

    seed_code.py <repo> [--source src/<pkg>] [--dry-run]

The coding loop records these links itself after every approved phase (.shared/code_links).
Use this to backfill phases approved before that, or another repo. It covers every
docs/subtask/phase-XX/*.json task whose "Phase XX sub-phase XX.YY:" commit is on HEAD, and a
code map of every Python module and Go package under --source (default: the only directory
under src/, or "." — the whole module — for a Go repo with go.mod at its root). It
reads plans and code at HEAD and writes with the repo's .archon/coding-loop.json knowledge
settings. --dry-run sends nothing. The last stdout line is a JSON report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.home() / ".archon/workflows/tasks/.shared"))
# A plain checkout of the workflow pack (CI, a fresh clone): its own .shared/, after the installed one.
sys.path.append(str(Path(__file__).resolve().parents[3] / ".shared"))
import code_links  # noqa: E402
import knowledge  # noqa: E402


def load_env() -> None:
    env = Path.home() / ".archon/.env"
    if env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)=(.*)", line)
            if m:
                os.environ.setdefault(m[1], m[2].strip().strip("\"'"))


def default_source(repo: Path) -> str | None:
    """The only directory under src/; else, for a Go module (go.mod at the root, packages under
    internal/ and cmd/), the whole module "."; else None."""
    dirs = sorted(p for p in (repo / "src").iterdir() if p.is_dir()) if (repo / "src").is_dir() else []
    if len(dirs) == 1:
        return str(dirs[0].relative_to(repo))
    return "." if not dirs and (repo / "go.mod").is_file() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo")
    ap.add_argument("--source", help="package directory to map (default: the only directory under src/,"
                                     " or the whole Go module when go.mod is at the root)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    source = a.source or default_source(repo)
    load_env()
    k = knowledge.settings(json.loads((repo / ".archon/coding-loop.json").read_text())["knowledge"])
    found = code_links.facts(repo, source=source, claim_max=k["claim_max"], rationale_max=k["rationale_max"])
    if a.dry_run:
        counts: dict = {}
        for f in found:
            kind = next(t for t in f["tags"] if t in ("rule", "task", "code-map"))
            counts[kind] = counts.get(kind, 0) + 1
        print(json.dumps({"would_record": counts}))
        return 0
    report = code_links.record(k, found)
    print(json.dumps(report))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
