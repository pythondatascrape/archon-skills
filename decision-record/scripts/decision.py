#!/usr/bin/env python3
"""Create the next numbered decision record, or check every record is complete.

new:   writes <dir>/<id>.json with every required field (empty) and status "proposed"; prints its path.
check: every record has a matching id and non-empty required fields, and ids have no gaps.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = ["id", "title", "status", "decision", "rationale", "sources"]


def pattern(fmt: str) -> re.Pattern:
    """D-{n:02d} -> ^D-(\\d+)$"""
    head, tail = re.split(r"\{n[^}]*\}", fmt, maxsplit=1)
    return re.compile(rf"^{re.escape(head)}(\d+){re.escape(tail)}$")


def records(d: Path, fmt: str) -> dict[int, Path]:
    rx = pattern(fmt)
    out = {}
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        m = rx.match(p.stem)
        if m:
            out[int(m.group(1))] = p
    return out


def new(d: Path, fmt: str, title: str) -> int:
    n = max(records(d, fmt), default=0) + 1
    rid = fmt.format(n=n)
    rec = {k: "" for k in REQUIRED} | {"id": rid, "title": title, "status": "proposed", "sources": [], "settles": []}
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(f"{d}/{rid}.json")
    return 0


def check(d: Path, fmt: str, required: list[str]) -> int:
    recs = records(d, fmt)
    problems = []
    for n, p in sorted(recs.items()):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{p.name}: not JSON ({e})")
            continue
        if rec.get("id") != p.stem:
            problems.append(f"{p.name}: id is {rec.get('id')!r}, expected {p.stem!r}")
        empty = [k for k in required if rec.get(k) in (None, "", [])]
        if empty:
            problems.append(f"{p.stem}: empty {', '.join(empty)}")
    gaps = sorted(set(range(1, max(recs, default=0) + 1)) - set(recs))
    problems += [f"missing {fmt.format(n=n)}" for n in gaps]
    for x in problems:
        print(x)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["new", "check"])
    ap.add_argument("--dir", default="docs/decisions")
    ap.add_argument("--id-format", default="D-{n:02d}")
    ap.add_argument("--title")
    ap.add_argument("--required", default=",".join(REQUIRED), help="comma-separated fields that must be filled")
    a = ap.parse_args()
    d = Path(a.dir)
    if a.action == "new":
        if not a.title:
            ap.error("new needs --title")
        return new(d, a.id_format, a.title)
    return check(d, a.id_format, [k for k in a.required.split(",") if k])


if __name__ == "__main__":
    sys.exit(main())
