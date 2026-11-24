"""Replace wrong project-memory facts with correcting facts, from a list the owner approved.

    python3 supersede_facts.py <approved.json> [--plan-out FILE.md] [--write]

Without --write it is a practice pass: it reads memory (read-only key), checks each fact and its
evidence, and shows exactly what would be written. Nothing is sent to `remember`.
With --write it first runs the same checks, refuses if any fact has a problem, then writes one
correcting fact per entry with a "supersedes" link to the old fact (the old fact stays stored
and is marked replaced), and finally checks recall.

approved.json:
    {"project": "<alias>", "repo": "<path to the repository>", "revision": "<40-hex commit on main>",
     "approved": "<who approved, when, where the list is>",
     "facts": [{"id": "<old fact id>", "old_claim": "...", "why": "...", "replacement": "..."}]}

Evidence is taken from the replacement text only: every repository path (with ":12" or
":12-14" lines, and ", :40" for more lines of the same file) must exist at `revision` (a file the
text names as removed before `revision`, or a bare file name never in the repository, is not
evidence and not a problem); "PR #N"
becomes the pull request's address; "commit abc1234" becomes that commit. A replacement too long
for one memory claim loses its trailing "Evidence: ..." sentence (the evidence is still attached);
the plan marks every claim that differs from the approved text. Keys come from ~/.archon/.env and
are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.home() / ".archon/workflows/tasks/.shared"))
sys.path.append(str(Path(__file__).resolve().parents[3] / ".shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import knowledge  # noqa: E402
import new_project  # noqa: E402

PATH = re.compile(r"(?<![\w/.~-])((?:src|test|tests|docs|scripts|release|vendor|\.github)/[\w./*-]*\w"
                  r"|[\w-]+\.(?:json|md|ts|mjs|js|py|sh))((?::\d+(?:-\d+)?)(?:,\s*:\d+(?:-\d+)?)*)?")
PR = re.compile(r"\bPR #(\d+)\b")
COMMIT = re.compile(r"\bcommit ([0-9a-f]{7,40})\b")
EVIDENCE_TAIL = re.compile(r"\s*Evidence:[^\n]*$")
TAG = "superseded-fact"


def load_env() -> None:
    env = Path.home() / ".archon/.env"
    if env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)=(.*)", line)
            if m:
                os.environ.setdefault(m[1], m[2].strip().strip("\"'"))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def fit_claim(text: str) -> tuple[str, str | None]:
    """(claim, problem): the approved text if memory accepts it as one claim, else the text
    without its trailing "Evidence: ..." sentence; problem is set when even that is refused."""
    t = " ".join(text.split())
    if knowledge.claim_problem(t) is None:
        return t, None
    short = EVIDENCE_TAIL.sub("", t).strip()
    return short, knowledge.claim_problem(short)


def evidence_of(text: str, repo: Path, revision: str, slug: str | None) -> tuple[list[dict], list[str], list[str]]:
    """(evidence, files, problems) for the paths, pull requests and commits the text names."""
    ev, files, problems, seen = [], [], [], set()
    for m in PATH.finditer(text):
        path = m[1]
        if "*" in path:
            continue
        blob = git(repo, "show", f"{revision}:{path}")
        if blob.returncode != 0:
            exists = git(repo, "cat-file", "-e", f"{revision}:{path}").returncode == 0  # a folder
            removed = git(repo, "log", "-1", "--format=%h", "--diff-filter=D", revision, "--", path).stdout.strip()
            if not exists and not removed and "/" in path:
                problems.append(f"{path} does not exist at {revision[:7]}")
            continue  # a folder, a file the text names as removed, or a bare name from elsewhere
        n_lines = len(blob.stdout.splitlines())
        kind = "test" if path.startswith(("test/", "tests/")) else "design_record" if path.startswith("docs/") else "source"
        ranges = re.findall(r"(\d+)(?:-(\d+))?", m[2] or "") or [(None, None)]
        for a, b in ranges:
            item = {"type": kind, "path": path, "revision": revision}
            if a:
                start, end = int(a), int(b or a)
                if not (1 <= start <= end <= n_lines):
                    problems.append(f"{path}:{a}{'-' + b if b else ''} is outside the file ({n_lines} lines)")
                    continue
                item |= {"line_start": start, "line_end": end}
            key = json.dumps(item, sort_keys=True)
            if key not in seen:
                seen.add(key)
                ev.append(item)
        if path not in files:
            files.append(path)
    for n in PR.findall(text):
        if slug:
            item = {"type": "issue", "reference": f"https://github.com/{slug}/pull/{n}"}
            if json.dumps(item, sort_keys=True) not in seen:
                seen.add(json.dumps(item, sort_keys=True))
                ev.append(item)
    for short in COMMIT.findall(text):
        full = git(repo, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}").stdout.strip()
        if not full:
            problems.append(f"commit {short} is not in the repository")
        elif json.dumps({"type": "commit", "revision": full}) not in seen:
            seen.add(json.dumps({"type": "commit", "revision": full}))
            ev.append({"type": "commit", "revision": full})
    if not ev:
        problems.append("names no evidence (a file on main, a pull request or a commit)")
    return ev, files, problems


def repo_slug(repo: Path) -> str | None:
    url = git(repo, "remote", "get-url", "origin").stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m[1] if m else None


def old_status(k: dict, project: str, fact_id: str, old_claim: str) -> tuple[str | None, str | None]:
    """(status, error): the old fact's status as recall shows it, or None when no query finds it.
    Recall answers within a size budget, so a long claim may crowd the fact out: the whole claim
    is tried first, then its label (the text before the first colon), then its first eight words."""
    label = old_claim.split(":", 1)[0]
    queries = [old_claim[:4000], label, " ".join(old_claim.split()[:8])]
    for q in dict.fromkeys(q for q in queries if q.strip()):
        try:
            r = knowledge.call_tool(k, "recall", {"project": project, "query": q, "limit": 50,
                                                  "include_evidence": False, "include_history": True},
                                    timeout=60, why="supersede-check")
        except knowledge.KnowledgeError as exc:
            return None, str(exc)
        hit = next((a for a in r.get("results") or [] if a.get("id") == fact_id), None)
        if hit:
            return hit.get("status") or "active", None
    return None, None


def plan(cfg: dict, k: dict) -> list[dict]:
    repo = Path(os.path.expanduser(cfg["repo"]))
    rev = git(repo, "rev-parse", "--verify", "--quiet", f"{cfg['revision']}^{{commit}}").stdout.strip()
    slug = repo_slug(repo)
    out, ids = [], set()
    for f in cfg["facts"]:
        claim, problem = fit_claim(f["replacement"])
        problems = [f"claim: {problem}"] if problem else []
        if not rev:
            problems.append(f"revision {cfg['revision']} is not in {repo}")
            ev, files = [], []
        else:
            ev, files, more = evidence_of(f["replacement"], repo, rev, slug)
            problems += more
        if " ".join(claim.split()).lower() == " ".join(f["old_claim"].split()).lower():
            problems.append("claim is the same as the old fact's; memory would treat it as a repeat")
        if f["id"] in ids:
            problems.append("listed twice")
        ids.add(f["id"])
        st, err = old_status(k, cfg["project"], f["id"], f["old_claim"])
        if err:
            problems.append(f"could not check the old fact: {err}")
        elif st is None:
            problems.append("old fact not found in memory (the id or its text is wrong)")
        elif st != "active":
            problems.append(f"old fact is already {st}")
        rationale = (f"Supersedes fact {f['id']}: {f['old_claim']}\nWhy: {f.get('why', '')}\n"
                     f"Approved: {cfg.get('approved', '')}. The old fact is kept and marked replaced.")
        out.append({"id": f["id"], "old_claim": f["old_claim"], "approved_text": f["replacement"], "claim": claim,
                    "changed": claim != " ".join(f["replacement"].split()), "rationale": rationale,
                    "evidence": ev, "files": files, "problems": problems})
    return out


def markdown(cfg: dict, items: list[dict]) -> str:
    bad = [i for i in items if i["problems"]]
    lines = [f"# Practice pass: correcting facts for {cfg['project']}", "",
             f"Nothing was written. {len(items)} facts would be written, each superseding one old fact; "
             f"{len(bad)} with problems; {sum(i['changed'] for i in items)} claims differ from the approved text "
             "(their trailing Evidence sentence moved into the attached evidence).", "",
             f"Evidence revision: `{cfg['revision']}` in `{cfg['repo']}`. Approved: {cfg.get('approved', '')}.", ""]
    for n, i in enumerate(items, 1):
        lines += [f"## {n}. supersedes `{i['id']}`", "", f"- **Old:** {i['old_claim'].strip()}",
                  f"- **New claim{' (shortened)' if i['changed'] else ''}:** {i['claim']}"]
        for e in i["evidence"]:
            where = e.get("path") or e.get("reference") or e.get("revision")
            if e.get("line_start"):
                where += f":{e['line_start']}" + (f"-{e['line_end']}" if e["line_end"] != e["line_start"] else "")
            lines.append(f"  - evidence ({e['type']}): {where}")
        lines += [f"- **Problems:** {'; '.join(i['problems'])}" if i["problems"] else "- **Problems:** none", ""]
    return "\n".join(lines) + "\n"


def write(cfg: dict, k: dict, items: list[dict]) -> dict:
    report = {"written": 0, "errors": [], "recall": []}
    for i in items:
        try:
            out = knowledge.remember(k, i["claim"], i["rationale"], i["evidence"], files=i["files"], tags=[TAG],
                                     links=[{"to": i["id"], "relation": "supersedes"}])
        except knowledge.KnowledgeError as exc:
            report["errors"].append(f"{i['id']}: {exc}")
            break
        report["written"] += 1
        new_id = out.get("atom_id") or out.get("id")
        # As the workflows search (replaced facts ranked down): the new fact must come before the old.
        q = {"project": cfg["project"], "query": i["old_claim"][:4000], "limit": 10, "include_evidence": False}
        ranked = [a.get("id") for a in knowledge.call_tool(k, "recall", q, timeout=60, why="supersede-verify")
                  .get("results") or []]
        hist = knowledge.call_tool(k, "recall", {**q, "include_history": True}, timeout=60, why="supersede-verify")
        old = next((a for a in hist.get("results") or [] if a.get("id") == i["id"]), None)
        new_first = new_id in ranked and (i["id"] not in ranked or ranked.index(new_id) < ranked.index(i["id"]))
        report["recall"].append({"old": i["id"], "new": new_id, "new_first": new_first,
                                 "old_status": old.get("status") if old else "not shown"})
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Replace wrong project-memory facts from an approved list.")
    ap.add_argument("approved")
    ap.add_argument("--plan-out")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.approved).read_text())
    load_env()
    names = new_project.names(cfg["project"])
    var = names["write_env"] if a.write else names["read_env"]
    if var not in os.environ:
        print(f"{var} is not set in ~/.archon/.env", file=sys.stderr)
        return 2
    k = knowledge.settings({"url": os.environ.get("RASRS_URL", "${RASRS_URL}"), "token": "${" + var + "}",
                            "project": cfg["project"]})
    items = plan(cfg, k)
    if a.plan_out:
        Path(a.plan_out).write_text(markdown(cfg, items))
    bad = [i for i in items if i["problems"]]
    summary = {"facts": len(items), "with_problems": len(bad), "shortened": sum(i["changed"] for i in items),
               "problems": {i["id"]: i["problems"] for i in bad}}
    if not a.write:
        print(json.dumps({"practice": True, **summary}))
        return 1 if bad else 0
    if bad:
        print(json.dumps({"written": 0, "refused": "some facts have problems; fix them and run the practice pass",
                          **summary}))
        return 1
    report = write(cfg, k, items)
    print(json.dumps({**summary, **report}))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
