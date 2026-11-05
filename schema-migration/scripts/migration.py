#!/usr/bin/env python3
"""Create the next numbered migration file, or check the numbering.

new <name>: writes <dir>/<format> with the next number and a slug of the name; prints its path.
check:      every file matches the format, numbers are unique and run 1..N with no gaps.
The format holds {n} (with optional spec, e.g. {n:04d}) and {slug}; the default is {n:04d}_{slug}.sql.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def rx(fmt: str) -> re.Pattern:
    parts = re.split(r"(\{n[^}]*\}|\{slug\})", fmt)
    body = "".join(r"(\d+)" if p.startswith("{n") else r"(.+)" if p == "{slug}" else re.escape(p) for p in parts)
    return re.compile(rf"^{body}$")


def scan(d: Path, fmt: str) -> tuple[dict[int, list[str]], list[str]]:
    numbered, bad = {}, []
    r = rx(fmt)
    for p in sorted(d.iterdir()) if d.is_dir() else []:
        if not p.is_file() or p.name.startswith("."):
            continue
        m = r.match(p.name)
        if m:
            numbered.setdefault(int(m.group(1)), []).append(p.name)
        else:
            bad.append(p.name)
    return numbered, bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["new", "check"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--format", default="{n:04d}_{slug}.sql")
    a = ap.parse_args()
    d = Path(a.dir)
    numbered, bad = scan(d, a.format)
    if a.action == "new":
        if not a.name:
            ap.error("new needs a name")
        slug = re.sub(r"[^a-z0-9]+", "_", a.name.lower()).strip("_")
        path = d / a.format.format(n=max(numbered, default=0) + 1, slug=slug)
        d.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)
        print(path)
        return 0
    problems = [f"{n:04d}: more than one file: {', '.join(v)}" for n, v in sorted(numbered.items()) if len(v) > 1]
    problems += [f"{n:04d}: missing" for n in sorted(set(range(1, max(numbered, default=0) + 1)) - set(numbered))]
    problems += [f"{b}: does not match {a.format}" for b in bad]
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
