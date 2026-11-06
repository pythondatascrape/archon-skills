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
A report path ending in .md is written as readable Markdown, with the data the check reads at
the end (an HTML comment, invisible when rendered); any other path is JSON. check reads either.
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


DATA_START, DATA_END = "<!-- evidence-data", "-->"


def markdown(rep: dict) -> str:
    """The report for people, then its data for check."""
    lines = [f"# Phase {rep['phase']} evidence", "", f"Commit: `{rep['commit']}`", ""]
    hw = rep.get("hardware", {})
    lines += [f"Machine: {hw.get('system', '')} {hw.get('release', '')} ({hw.get('machine', '')})", ""]
    if rep.get("versions"):
        lines += ["## Versions", "", "| Tool | Version |", "| --- | --- |"]
        lines += [f"| {k} | {v} |" for k, v in rep["versions"].items()] + [""]
    checks = [k for k in ("result", "advisory") if k in rep]
    if checks:
        lines += ["## Checks", "", "| Check | Command | Outcome |", "| --- | --- | --- |"]
        lines += [f"| {k} | `{rep[k]['command']}` | {rep[k]['outcome']} |" for k in checks] + [""]
    extra = {k: v for k, v in rep.items() if k not in ("schema_version", "phase", "commit", "versions", "hardware",
                                                       "result", "advisory", "owner", "acceptance_criteria")}
    for k, v in extra.items():
        lines += [f"## {k}", "", "```json", json.dumps(v, indent=2), "```", ""]
    if rep.get("owner"):
        lines += ["## Owner-supplied facts", ""] + [f"- {k}: {v}" for k, v in rep["owner"].items()] + [""]
    lines += ["## Acceptance criteria", "", "| Criterion | Requirements | Tests |", "| --- | --- | --- |"]
    lines += [f"| {a['id']} | {', '.join(a['requirements'])} | {'<br>'.join(a['tests'])} |"
              for a in rep.get("acceptance_criteria", [])]
    return "\n".join(lines) + "\n\n" + DATA_START + "\n" + json.dumps(rep, indent=1) + "\n" + DATA_END + "\n"


def read_report(path: Path) -> dict | None:
    """The report's data, from a JSON report or a Markdown report's data block; None if unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if path.suffix == ".md":
        start = text.rfind(DATA_START)
        if start < 0:
            return None
        text = text[start + len(DATA_START):text.find(DATA_END, start)]
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


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
    out.write_text(markdown(rep) if out.suffix == ".md" else json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(out.relative_to(root))
    return 1 if failed else 0


def check(args) -> int:
    cfg, root = load(args)
    path = cfg["report"].format(phase=args.phase)
    rep = read_report(root / path)
    if rep is None:
        print(f"{path}: missing, or not written by this skill; run `evidence.py build --phase {args.phase}` "
              "with the same config to write it")
        return 1
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
