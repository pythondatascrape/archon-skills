#!/usr/bin/env python3
"""Write or check a phase's evidence report: commit, tool versions, settings, machine, the result
of the phase's test command, an optional advisory check, owner-supplied facts, and each acceptance
criterion with the requirements and tests that cover it (from the phase plan).

Config (JSON, all keys optional; {phase} is replaced):
  plan               plan path              default docs/tasks/phase-{phase}.json
  report             report path            default evidence/phase-{phase}.json
  versions           {name: command}        each command's first output line is recorded
  result_command     command that must pass default none
  advisory_command   command, e.g. an audit default none
  static             {section: object}      copied into the report as is
  owner_inputs       {"file": path, "required": [keys]}  facts only the owner can supply
  acceptance_pattern regex for criterion ids default ^AC-
Exit: 0 written/ok, 1 a command failed or a check failed, 2 owner facts missing (all listed).
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

DEFAULTS = {"plan": "docs/tasks/phase-{phase}.json", "report": "evidence/phase-{phase}.json",
            "versions": {}, "result_command": None, "advisory_command": None, "static": {},
            "owner_inputs": None, "acceptance_pattern": "^AC-"}


def sh(cmd: str, root: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def test_exists(root: Path, ref: str) -> bool:
    file, name = ref.split("::", 1)
    try:
        text = (root / file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text) is not None


def criteria(plan: dict, pattern: str) -> list[dict]:
    acs: dict[str, dict] = {}
    for t in plan.get("tasks", []):
        ids = t.get("requirements", [])
        tests = {f"{x['file']}::{x['name']}" for x in t.get("tests", [])}
        for ac in (r for r in ids if re.search(pattern, r)):
            e = acs.setdefault(ac, {"id": ac, "requirements": set(), "tests": set()})
            e["requirements"].update(r for r in ids if not re.search(pattern, r))
            e["tests"].update(tests)
    return [{"id": k, "requirements": sorted(v["requirements"]), "tests": sorted(v["tests"])}
            for k, v in sorted(acs.items())]


def load(args) -> tuple[dict, Path]:
    root = Path(args.root)
    cfg = dict(DEFAULTS)
    if args.config:
        cfg.update({k: v for k, v in json.loads((root / args.config).read_text(encoding="utf-8")).items()})
    return cfg, root


def build(args) -> int:
    cfg, root = load(args)
    ph = args.phase
    owner = {}
    if cfg["owner_inputs"]:
        path = cfg["owner_inputs"]["file"].format(phase=ph)
        try:
            owner = json.loads((root / path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            owner = {}
        missing = [k for k in cfg["owner_inputs"].get("required", []) if owner.get(k) in (None, "")]
        if missing:
            print(f"Owner facts needed in {path}:")
            for k in missing:
                print(f"- {k}")
            return 2
    plan = json.loads((root / cfg["plan"].format(phase=ph)).read_text(encoding="utf-8"))
    rep = {"schema_version": 1, "phase": ph, "commit": sh("git rev-parse HEAD", root)[1]}
    rep["versions"] = {k: (sh(c, root)[1].splitlines() or [""])[0] for k, c in cfg["versions"].items()}
    rep.update(cfg["static"])
    rep["hardware"] = {"system": platform.system(), "release": platform.release(), "machine": platform.machine()}
    failed = False
    if cfg["result_command"]:
        code, _ = sh(cfg["result_command"], root)
        rep["result"] = {"command": cfg["result_command"], "outcome": "passed" if code == 0 else "failed",
                         "exit_code": code}
        failed |= code != 0
    if cfg["advisory_command"]:
        code, text = sh(cfg["advisory_command"], root)
        rep["advisory"] = {"command": cfg["advisory_command"], "outcome": "passed" if code == 0 else "failed",
                           "output": text[-2000:]}
        failed |= code != 0
    if owner:
        rep["owner"] = owner
    rep["acceptance_criteria"] = criteria(plan, cfg["acceptance_pattern"])
    out = root / cfg["report"].format(phase=ph)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(out.relative_to(root))
    return 1 if failed else 0


def check(args) -> int:
    cfg, root = load(args)
    rep = json.loads((root / cfg["report"].format(phase=args.phase)).read_text(encoding="utf-8"))
    problems = [f"{ac['id']}: {ref} not found" for ac in rep.get("acceptance_criteria", [])
                for ref in ac["tests"] if not test_exists(root, ref)]
    problems += [f"{k}: {rep[k]['command']} {rep[k]['outcome']}" for k in ("result", "advisory")
                 if k in rep and rep[k].get("outcome") == "failed"]
    for p in problems:
        print(p)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["build", "check"])
    ap.add_argument("--phase", required=True)
    ap.add_argument("--config", help="config JSON (see above)")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    return build(a) if a.action == "build" else check(a)


if __name__ == "__main__":
    sys.exit(main())
