"""Wire a new repo to Archon, the coding loop and the local rasrs memory server, in one call.

    python3 new_project.py --repo PATH --alias ALIAS [--name NAME] [--lang go] [--dry-run]

Steps, each skipped when already done:
  1. refuse while an Archon run is running or paused (the server stops briefly);
  2. stop the server, register the project, create the project's OWN read and write tokens
     (principals remote:archon_read_<alias> / remote:archon_write_<alias>), start the server;
  3. save the tokens into ~/.archon/.env as RASRS_<ALIAS>_READ_TOKEN / _WRITE_TOKEN (mode 600),
     parsed in code and never printed;
  4. write .archon/coding-loop.json and .archon/compile-phase-tasks.json: a starter for the
     language when missing, then the rasrs wiring merged in (other keys are kept);
  5. print status.py --repo for the result.
Per-project tokens keep one project's coders out of another project's memory. Restart Archon
afterwards so it loads the new .env lines (reference.md › Server control).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status  # noqa: E402

SECRET = status.SECRET
ENV_FILE = status.ENV_FILE
ALIAS = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")


class SetupError(ValueError):
    """Something that stops the setup; the message says what to do."""


def names(alias: str) -> dict[str, str]:
    """The project's own principals (no hyphens allowed) and .env variable names."""
    flat = re.sub(r"[^a-z0-9_]", "_", alias.lower())
    return {"read_principal": f"remote:archon_read_{flat}", "write_principal": f"remote:archon_write_{flat}",
            "read_env": f"RASRS_{flat.upper()}_READ_TOKEN", "write_env": f"RASRS_{flat.upper()}_WRITE_TOKEN"}


def check_alias(alias: str, taken: set[str]) -> None:
    if not ALIAS.fullmatch(alias or ""):
        raise SetupError(f"alias {alias!r}: use 1-40 lowercase letters, digits, '-' or '_', starting with a "
                         "letter or digit")
    if alias in taken:
        raise SetupError(f"alias {alias!r} is already registered in rasrs; pick another")


def check_same_repo(project: dict, repo: Path) -> None:
    """An alias already registered must belong to this repo, not be reused for another one."""
    path = (project.get("repository") or {}).get("path")
    if path and Path(path).resolve() != Path(repo).resolve():
        raise SetupError(f"alias {project['aliases'][0]!r} is registered to {path}, not {repo}; pick another alias")


def set_env(text: str, updates: dict[str, str]) -> str:
    """Replace each KEY=... line in place; append keys that are not there."""
    lines, left = text.splitlines(), dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0] if "=" in line and not line.lstrip().startswith("#") else None
        if key in left:
            lines[i] = f"{key}={left.pop(key)}"
    lines += [f"{k}={v}" for k, v in left.items()]
    return "\n".join(lines) + "\n"


def _hint(alias: str, review: bool) -> str:
    if review:
        return (f'Project memory (rasrs MCP, read-only): call recall with project "{alias}" and the changed area '
                "to find recorded decisions (tag decision) and past findings, and check the change does not "
                "contradict a decision whose evidence still holds. A recalled fact is a hint, not authority.")
    return (f'Project memory (rasrs MCP, read-only): before changing code, call recall with project "{alias}" '
            "and a short query naming the task's area, to find recorded decisions and pitfalls. A recalled fact "
            "is a hint, not authority: the plan and the tests decide.")


def _with_hint(current, hint: str) -> str:
    current = current if isinstance(current, str) else ""
    return current if hint in current else (f"{current} {hint}".strip())


def wire(loop: dict, comp: dict, alias: str) -> tuple[dict, dict]:
    """The two configs with the rasrs server, hints and writer for alias merged in."""
    n, loop, comp = names(alias), copy.deepcopy(loop), copy.deepcopy(comp)
    server = {"url": "${RASRS_URL}", "headers": {"Authorization": f"Bearer ${{{n['read_env']}}}"}}
    loop.setdefault("mcp_servers", {})["rasrs"] = {**server, "roles": ["coder", "review"]}
    loop["mcp_hint"] = _with_hint(loop.get("mcp_hint"), _hint(alias, review=False))
    loop["review_mcp_hint"] = _with_hint(loop.get("review_mcp_hint"), _hint(alias, review=True))
    loop["knowledge"] = {"url": "${RASRS_URL}", "token": f"${{{n['write_env']}}}", "project": alias}
    comp.setdefault("mcp_servers", {})["rasrs"] = copy.deepcopy(server)
    comp["mcp_hint"] = _with_hint(comp.get("mcp_hint"), _hint(alias, review=False))
    return loop, comp


GO_LIST = ("go list -f '{{.ImportPath}}{{\"\\t\"}}{{.Dir}}{{\"\\t\"}}{{join .Imports \" \"}} "
           "{{join .TestImports \" \"}} {{join .XTestImports \" \"}}' ./...")


def starter(lang: str) -> dict:
    """A coding-loop.json starter with the language's gates; {} when there is none for it."""
    if lang == "python":  # uv + pytest, tests named by file
        return {
            "phase_validation": ["uv run pytest -q"],
            "suite_commands": ["uv run pytest -q"],  # run once in phase validation, not in each task's gate
            "bash_guard": [{"deny": r"\bpytest\b", "unless": r"\btests/\S+\.py|\s-k\s|\|\s*(tail|head|grep)\b|>\s*\S",
                            "reason": "a whole-suite pytest floods your context and the controller runs the full "
                                      "suite itself; run your test file (uv run pytest -q tests/test_x.py), add "
                                      "-k NAME, or pipe through | tail -n 60"}],
            "plan_lint": {"test_filter_flag": "-k"},
        }
    if lang != "go":
        return {}
    return {
        "phase_validation": ["go vet ./...", 'test -z "$(gofmt -l .)"', "go mod tidy -diff",
                             "go test -count=1 ./..."],
        "suite_commands": ["go test -count=1 ./..."],  # run once in phase validation, not in each task's gate
        "task_checks": {"changed_dir": {"glob": "*.go", "command": "go test -count=1 ./{dir}/"},
                        "importers": {"glob": "*.go", "list": GO_LIST, "command": "go test -count=1 ./{dir}/"}},
        "bash_guard": [{"deny": r"\bgo test\b.*\./\.\.\.", "unless": r"-run\b|\|\s*(tail|head|grep)\b|>\s*\S",
                        "reason": "a whole-repo go test floods your context and the controller runs the full suite "
                                  "itself; run your package (go test -count=1 ./x/), add -run 'TestName', or pipe "
                                  "through | tail -n 60"}],
        "plan_lint": {"test_filter_flag": "-run"},
        "api_summary": "go doc -short ./{dir}",
    }


# ---- side effects ----------------------------------------------------------------------------

def _run(*cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=120)
    if check and p.returncode != 0:
        raise SetupError(f"{' '.join(cmd[:3])} failed: {(p.stderr or p.stdout).strip()[:300]}")
    return p


def _rasrs(*args: str) -> dict | list:
    out = _run(status.rasrs_bin(), "--json", *args).stdout
    return json.loads(out) if out.strip() else {}


def _live_runs(ignore: str = "") -> list[str]:
    """Running or paused Archon runs; `ignore` (a run id) leaves out the run that is calling."""
    out = _run("archon", "workflow", "runs", check=False).stdout
    mine = ignore[:8]
    return [ln for ln in out.splitlines() if re.search(r"\b(running|paused)\b", ln)
            and not (mine and ln.split() and ln.split()[0] == mine)]


def registry_path() -> Path:
    """The shared list of connected repos the workflows read (MEMORY_PROJECTS_FILE moves it)."""
    return Path(os.environ.get("MEMORY_PROJECTS_FILE") or Path.home() / ".archon" / "memory-projects.json")


def registry_entry(alias: str) -> dict:
    """Only the rasrs settings for each workflow: no starter gates, so any language keeps its own."""
    loop, comp = wire({}, {}, alias)
    return {"alias": alias, "coding-loop": loop, "compile-phase-tasks": comp}


def record_registry(path: Path, repo: Path, alias: str) -> None:
    """Add or refresh one repo in the shared list (mode 600), keeping the others."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    projects = doc.get("projects") if isinstance(doc.get("projects"), dict) else {}
    projects[str(repo)] = registry_entry(alias)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"projects": projects}, indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def _server(action: str) -> None:
    uid, label = os.getuid(), status.LABEL
    if action == "stop":
        _run("launchctl", "bootout", f"gui/{uid}/{label}", check=False)
        return
    _run("launchctl", "bootstrap", f"gui/{uid}", str(status.PLIST), check=False)
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8787/livez", timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise SetupError("the rasrs server did not come back; see ~/Library/Logs/rasrs.log")


def _projects() -> list[dict]:
    out = _rasrs("project", "list")
    return out.get("projects", out) if isinstance(out, dict) else out


def _token(principal: str, project_id: str, actions: str) -> str:
    out = _rasrs("token", "create", "--principal", principal, "--project", project_id, "--actions", actions,
                 "--expires-in", "8760h")
    tok = out.get("token") if isinstance(out, dict) else None
    if not tok:
        raise SetupError(f"token create for {principal} returned no token")
    return tok


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--alias", required=True)
    ap.add_argument("--name", help="project name (default: <alias>-project; must differ from the alias)")
    ap.add_argument("--lang", default="go", help="starter gates for this language (go, python; others get none)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change; touch nothing")
    ap.add_argument("--no-repo-files", action="store_true",
                    help="write no .archon/ files in the repo (the workflows read the shared list instead)")
    ap.add_argument("--registry", action="store_true",
                    help="record the repo in the shared list of connected repos (MEMORY_PROJECTS_FILE)")
    ap.add_argument("--ignore-run", default="", help="a run id to leave out of the live-run check (the caller)")
    a = ap.parse_args()
    repo, alias = a.repo.expanduser().resolve(), a.alias
    name = a.name or f"{alias}-project"
    try:
        if not (repo / ".git").exists():
            raise SetupError(f"{repo} is not a git repository")
        projects = _projects()
        mine = [p for p in projects if alias in (p.get("aliases") or [])]
        check_alias(alias, taken=set() if mine else {a for p in projects for a in (p.get("aliases") or [])})
        if mine:
            check_same_repo(mine[0], repo)
        n = names(alias)
        env = status.read_env()
        need_tokens = not (env.get(n["read_env"]) and env.get(n["write_env"]))
        loop_p, comp_p = repo / ".archon" / "coding-loop.json", repo / ".archon" / "compile-phase-tasks.json"
        loop = json.loads(loop_p.read_text()) if loop_p.exists() else starter(a.lang)
        comp = json.loads(comp_p.read_text()) if comp_p.exists() else {}
        loop2, comp2 = wire(loop, comp, alias)
        plan = [f"register project {name!r} (alias {alias})" if not mine else f"project {alias} is registered",
                f"create tokens {n['read_principal']}, {n['write_principal']} -> ~/.archon/.env "
                f"{n['read_env']}, {n['write_env']}" if need_tokens else "tokens are in ~/.archon/.env"]
        if not a.no_repo_files:
            plan += [f"write {loop_p.relative_to(repo)}" if loop2 != loop or not loop_p.exists() else "coding-loop.json wired",
                     f"write {comp_p.relative_to(repo)}" if comp2 != comp or not comp_p.exists()
                     else "compile-phase-tasks.json wired"]
        if a.registry:
            plan.append(f"record {repo} as {alias} in {registry_path()}")
        print("\n".join(f"- {s}" for s in plan))
        if a.dry_run:
            return
        if (not mine or need_tokens) and (live := _live_runs(a.ignore_run)):
            raise SetupError("an Archon run is running or paused; wait for it to end (the server stops briefly):\n  "
                             + "\n  ".join(live))
        if not mine or need_tokens:
            _server("stop")
            try:
                if not mine:
                    origin = _run("git", "-C", str(repo), "remote", "get-url", "origin", check=False).stdout.strip()
                    args = ["project", "register", "--name", name, "--alias", alias, "--path", str(repo),
                            "--default-branch", "main"] + (["--origin", origin] if origin else [])
                    _rasrs(*args)
                pid = next(p["id"] for p in _projects() if alias in (p.get("aliases") or []))
                if need_tokens:
                    updates = {n["read_env"]: _token(n["read_principal"], pid, "read"),
                               n["write_env"]: _token(n["write_principal"], pid, "read,remember")}
                    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
                    ENV_FILE.write_text(set_env(text, updates), encoding="utf-8")
                    ENV_FILE.chmod(0o600)
            finally:
                _server("start")
        if not a.no_repo_files:
            _write_json(loop_p, loop2)
            _write_json(comp_p, comp2)
        if a.registry:
            record_registry(registry_path(), repo, alias)
    except SetupError as exc:
        sys.exit(f"new_project: {exc}")
    print(_run(sys.executable, str(Path(__file__).parent / "status.py"), "--repo", str(repo), check=False).stdout)
    print("Next: restart Archon so it loads the new .env lines"
          + ("." if a.no_repo_files else ", then commit .archon/ on a branch."))


if __name__ == "__main__":
    main()
