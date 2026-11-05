#!/usr/bin/env python3
"""Keep a registry of file fingerprints (path -> sha256) inside a JSON file up to date.

The map is found by a JSON pointer, e.g. /versions/1/files. Everything else in the file is kept.
check:  list every path whose fingerprint is stale or whose file is missing (exit 1 if any).
update: recompute them all (and --add new paths); refuses, changing nothing, if a file is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def resolve(doc, pointer: str):
    node = doc
    for part in [p.replace("~1", "/").replace("~0", "~") for p in pointer.strip("/").split("/") if p]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if not isinstance(node, dict):
        raise KeyError(pointer)
    return node


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["check", "update"])
    ap.add_argument("--file", required=True, help="the JSON file holding the registry")
    ap.add_argument("--pointer", default="", help="JSON pointer to the path->sha256 map (default: the whole file)")
    ap.add_argument("--add", nargs="*", default=[], help="paths to add (update only)")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root)
    doc = json.loads((root / a.file).read_text(encoding="utf-8"))
    try:
        reg = resolve(doc, a.pointer)
    except (KeyError, IndexError, ValueError):
        print(f"no path->sha256 map at {a.pointer or '/'} in {a.file}")
        return 2
    paths = sorted(set(reg) | set(a.add if a.action == "update" else []))
    missing = [p for p in paths if not (root / p).is_file()]
    stale = [p for p in paths if p not in missing and reg.get(p) != sha(root / p)]
    for p in missing:
        print(f"{p}: file missing")
    if a.action == "check":
        for p in stale:
            print(f"{p}: fingerprint is stale")
        return 1 if missing or stale else 0
    if missing:
        return 1
    for p in paths:
        reg[p] = sha(root / p)
    (root / a.file).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"{len(stale)} updated, {len(paths)} registered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
