"""Read-only status of the local rasrs memory server and its Archon wiring, in one call.

    python3 status.py [--repo PATH] [--json]

Reports: is the server up and loaded at login; is ~/.archon/.env complete, private and loaded
by the running Archon; do both tokens still authenticate and when do they expire; what the store
holds; how a repo is wired (with --repo); what the coding loop last recorded for it. Every
problem comes with its fix. Never prints a token: only whether it is set and its length.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENV_FILE = Path.home() / ".archon" / ".env"
LABEL = "com.rasrs.serve"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
TOKENS = ("RASRS_READ_TOKEN", "RASRS_WRITE_TOKEN")
WARN_DAYS = 30
SECRET = re.compile(r"Bearer\s+(?!\$)[A-Za-z0-9_\-.]{20,}")


def rasrs_bin() -> str:
    return shutil.which("rasrs") or str(Path.home() / ".local" / "bin" / "rasrs")


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.lstrip().startswith("#"))


def _cli(*args: str):
    p = subprocess.run([rasrs_bin(), "--json", *args], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout).strip()[:300]}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"error": p.stdout[:300]}


def _auth(url: str, token: str) -> str:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    req = urllib.request.Request(url, body, {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                             "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=5):
            return "ok"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError):
        return "unreachable"


def _archon_started() -> datetime | None:
    pid = subprocess.run(["pgrep", "-f", "archon serve"], capture_output=True, text=True).stdout.split()
    if not pid:
        return None
    out = subprocess.run(["ps", "-o", "lstart=", "-p", pid[0]], capture_output=True, text=True).stdout.strip()
    try:
        return datetime.strptime(out, "%a %b %d %H:%M:%S %Y").astimezone(timezone.utc)
    except ValueError:
        return None


def knowledge_outcomes(repo: Path) -> list[dict]:
    """What the coding loop last recorded per phase for this repo (state["knowledge"])."""
    out = []
    for f in sorted(Path.home().glob(f".archon/workspaces/*/{repo.name}/state/coding-loop/phase-*/state.json")):
        try:
            k = json.loads(f.read_text(encoding="utf-8")).get("knowledge")
        except (OSError, json.JSONDecodeError):
            continue
        if k:
            out.append({"phase": f.parent.name, **k})
    return out


def collect(repo: Path | None = None) -> dict:
    env = read_env()
    url = env.get("RASRS_URL", "")
    base = url.rsplit("/mcp", 1)[0] if url.endswith("/mcp") else url
    try:
        with urllib.request.urlopen(f"{base}/livez", timeout=3) as r:
            livez = r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        livez = False
    launchd = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
                             capture_output=True).returncode == 0 if PLIST.exists() else False
    try:
        st = ENV_FILE.stat()
        mode, mtime = oct(st.st_mode & 0o777)[2:], datetime.fromtimestamp(st.st_mtime, timezone.utc)
    except OSError:
        mode, mtime = None, None
    tokens = _cli("token", "list")
    wired = wiring(repo) if repo else None
    names = tuple(dict.fromkeys(TOKENS + tuple((wired or {}).get("token_vars", []))))
    facts = {
        "server": {"livez": livez, "launchd": launchd, "url": url, "binary": rasrs_bin()},
        "env": {"file_mode": mode, "mtime": mtime,
                "vars": {k: (v if k == "RASRS_URL" else len(v)) for k, v in env.items()
                         if k in ("RASRS_URL",) + names and v}},
        "archon": {"started": _archon_started()},
        "auth": {t: _auth(url, env[t]) if url and env.get(t) else "not set" for t in names},
        "tokens": tokens.get("tokens", []) if isinstance(tokens, dict) else [],
        "stats": _cli("stats"),
    }
    if repo:
        facts["repo"] = {"path": str(repo), **(wired or {}), "recorded": knowledge_outcomes(repo)}
    return facts


def problems(facts: dict, now: datetime) -> list[dict]:
    out = []

    def add(problem, fix):
        out.append({"problem": problem, "fix": fix})

    start = "launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rasrs.serve.plist"
    server, env = facts["server"], facts["env"]
    if not server.get("launchd"):
        add("the server is not loaded (it will not start at login)", f"`{start}`; log: ~/Library/Logs/rasrs.log")
    elif not server.get("livez"):
        add("the server is not answering", f"`launchctl kickstart -k gui/$(id -u)/{LABEL}` (or `{start}`); "
                                           "read ~/Library/Logs/rasrs.log")
    for name in dict.fromkeys(("RASRS_URL",) + TOKENS + tuple((facts.get("repo") or {}).get("token_vars", []))):
        if name not in env.get("vars", {}):
            add(f"{name} is not set", f"add it to ~/.archon/.env, then restart Archon")
    if env.get("file_mode") and env["file_mode"] != "600":
        add(f"~/.archon/.env is mode {env['file_mode']}, readable by others", "`chmod 600 ~/.archon/.env`")
    started = facts.get("archon", {}).get("started")
    if started and env.get("mtime") and env["mtime"] > started:
        add("~/.archon/.env changed after Archon started, so runs use the old values",
            "restart Archon when no run is active (see reference.md)")
    if server.get("livez"):
        for name, result in facts.get("auth", {}).items():
            if result not in ("ok", "not set"):
                add(f"{name} is refused by the server ({result})",
                    "stop the server, `rasrs token create …` (reference.md › Tokens), update ~/.archon/.env, "
                    "start the server, restart Archon")
    for t in facts.get("tokens", []):
        try:
            left = (datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00")) - now).days
        except (KeyError, ValueError):
            continue
        if left < WARN_DAYS:
            add(f"token {t.get('principal')} expires in {left} days", "renew it: reference.md › Tokens (`token create`)")
    index = (facts.get("stats") or {}).get("index") or {}
    if index.get("state") not in (None, "healthy"):
        add(f"the search index is {index['state']}", "stop the server, `rasrs reindex`, start the server")
    for p in (facts.get("repo") or {}).get("problems", []):
        add(p, "edit the repo's .archon config (reference.md › Wiring a repo)")
    for k in (facts.get("repo") or {}).get("recorded", []):
        if k.get("errors"):
            add(f"{k['phase']}: the coding loop could not record facts: {k['errors'][0][:160]}",
                "start the server; the run itself is fine (SKILL.md › Recording failed)")
    return out


def wiring(repo: Path) -> dict:
    """Which workflow steps of a repo use rasrs, from its .archon configs."""
    def load(name):
        try:
            return json.loads((repo / ".archon" / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    loop, comp = load("coding-loop.json"), load("compile-phase-tasks.json")
    servers = {n: s for n, s in (loop.get("mcp_servers") or {}).items() if "url" in s}
    roles = {r for s in servers.values() for r in s.get("roles", ["coder"])}
    problems = [f"a secret is written into .archon/{name}; use a ${{VAR}} from ~/.archon/.env instead"
                for name in ("coding-loop.json", "compile-phase-tasks.json")
                if (repo / ".archon" / name).exists() and SECRET.search((repo / ".archon" / name).read_text())]
    k = loop.get("knowledge") or {}
    refs = json.dumps([servers, k, comp.get("mcp_servers") or {}])
    token_vars = sorted({v for v in re.findall(r"\$\{([A-Z0-9_]+)\}", refs) if v.startswith("RASRS_") and v.endswith("_TOKEN")})
    return {"coders": "coder" in roles, "reviewers": "review" in roles, "writer": k.get("project"),
            "interview": any("url" in s for s in (comp.get("mcp_servers") or {}).values()), "problems": problems,
            "token_vars": token_vars}


def render(facts: dict, found: list[dict]) -> str:
    s, st = facts["server"], facts.get("stats") or {}
    lines = [f"Server: {'up' if s['livez'] else 'DOWN'} at {s['url'] or '(RASRS_URL not set)'}; "
             f"{'starts at login' if s['launchd'] else 'NOT loaded at login'}"]
    for p in st.get("projects", []):
        by = p.get("atoms_by_status", {})
        lines.append(f"Project {p['name']}: {p['atoms']} facts ({by.get('active', 0)} active, "
                     f"{by.get('superseded', 0)} superseded); last write {p.get('last_written_at', '-')}")
    if st.get("index"):
        lines.append(f"Search index: {st['index'].get('state')}")
    lines.append("Tokens in ~/.archon/.env: " + ", ".join(
        f"{t} {'set' if t in facts['env']['vars'] else 'MISSING'} ({facts['auth'].get(t)})" for t in TOKENS))
    for t in facts.get("tokens", []):
        lines.append(f"  {t.get('principal')}: {','.join(t.get('actions', []))}, expires {t.get('expires_at', '?')[:10]}")
    r = facts.get("repo")
    if r:
        lines.append(f"Repo {r['path']}: coders {'yes' if r['coders'] else 'no'}, reviewers "
                     f"{'yes' if r['reviewers'] else 'no'}, interview {'yes' if r['interview'] else 'no'}, "
                     f"writer {r['writer'] or 'off'}")
        for k in r["recorded"][-3:]:
            lines.append(f"  {k['phase']}: recorded {k.get('recorded', 0)}, skipped {k.get('skipped', 0)}, "
                         f"errors {len(k.get('errors', []))} (commit {str(k.get('commit', ''))[:9]})")
    lines.append("Problems: none" if not found else "Problems:")
    lines += [f"  - {p['problem']}\n    fix: {p['fix']}" for p in found]
    return "\n".join(lines)


def main() -> None:
    args = sys.argv[1:]
    repo = Path(args[args.index("--repo") + 1]).expanduser().resolve() if "--repo" in args else None
    facts = collect(repo)
    found = problems(facts, datetime.now(timezone.utc))
    if "--json" in args:
        print(json.dumps({"facts": facts, "problems": found}, default=str, indent=1))
    else:
        print(render(facts, found))


if __name__ == "__main__":
    main()
