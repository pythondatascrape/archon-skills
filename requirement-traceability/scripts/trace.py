#!/usr/bin/env python3
"""Trace each requirement of a phase plan to the tests that cover it, and check each test exists.

A plan is JSON with "tasks", each with "requirements" (ids) and "tests" ({"name", "file"}).
Exit 0 when every traced requirement has a test and every test is found in its file, else 1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def test_exists(root: Path, file: str, name: str) -> bool:
    """The test's name appears as a whole word in its file (each part, for TestX/case)."""
    try:
        text = (root / file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # A Go subtest TestX/case is `func TestX` plus `t.Run("case", ...)`: every part must appear.
    return all(re.search(rf"(?<![\w]){re.escape(part)}(?![\w])", text) for part in name.split("/") if part)


def trace(plan: dict, root: Path, pattern: str | None = None) -> dict:
    reqs: dict[str, set[str]] = {}
    tasks_of: dict[str, set[str]] = {}
    for t in plan.get("tasks", []):
        tests = {f"{x['file']}::{x['name']}" for x in t.get("tests", [])}
        for r in t.get("requirements", []):
            if pattern and not re.search(pattern, r):
                continue
            reqs.setdefault(r, set()).update(tests)
            tasks_of.setdefault(r, set()).add(t.get("task_id", "?"))
    problems = []
    for r in sorted(reqs):
        if not reqs[r]:
            problems.append(f"{r}: no test (tasks {', '.join(sorted(tasks_of[r]))})")
        for ref in sorted(reqs[r]):
            file, name = ref.split("::", 1)
            if not test_exists(root, file, name):
                problems.append(f"{r}: {ref} not found (tasks {', '.join(sorted(tasks_of[r]))})")
    return {"requirements": {r: sorted(v) for r, v in sorted(reqs.items())}, "problems": problems}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True, help="phase plan JSON")
    ap.add_argument("--pattern", help="trace only requirement ids matching this regex")
    ap.add_argument("--out", help="also write the trace as JSON here")
    ap.add_argument("--root", default=".", help="project root (default: current folder)")
    a = ap.parse_args()
    root = Path(a.root)
    result = trace(json.loads((root / a.plan).read_text(encoding="utf-8")), root, a.pattern)
    if a.out:
        (root / a.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for p in result["problems"]:
        print(p)
    print(f"{len(result['requirements'])} requirements, {len(result['problems'])} problems")
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
