"""Look facts up in project memory with the read-only token. Never writes.

    python3 recall.py "query" [--project ALIAS] [--limit N] [--json]

The project defaults to "rasrs". Address and token come from ~/.archon/.env: RASRS_URL, and
RASRS_READ_TOKEN for rasrs or the project's own RASRS_<ALIAS>_READ_TOKEN (new_project.py writes
it); the token is never printed. A recalled fact is a hint: check the file its
evidence points to before relying on it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.home() / ".archon" / "workflows" / "tasks" / ".shared"))
# A plain checkout of the workflow pack (CI, a fresh clone): its own .shared/, after the installed one.
sys.path.append(str(Path(__file__).resolve().parents[3] / ".shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def render(result: dict) -> str:
    items = result.get("results") or []
    if not items:
        return "No facts found."
    lines = []
    for i, a in enumerate(items, 1):
        ev = ", ".join(e.get("path") or e.get("revision") or e.get("reference") or e.get("type", "")
                       for e in a.get("evidence") or [])
        lines.append(f"{i}. [{a.get('status', '?')}] {a.get('claim', '')}")
        if a.get("conflict"):
            lines.append(f"   may conflict with {', '.join(a.get('conflicts_with') or []) or 'another fact'}")
        lines.append(f"   evidence: {ev or '-'} | id: {a.get('id', '')}")
        if a.get("rationale"):
            lines.append(f"   why: {a['rationale'][:300].replace(chr(10), ' ')}")
    return "\n".join(lines)


def token_var(project: str, env: dict) -> str:
    """The read token variable for a project: its own one, or the shared one for rasrs."""
    import new_project
    own = new_project.names(project)["read_env"]
    if own in env:
        return own
    if project == "rasrs":
        return "RASRS_READ_TOKEN"
    sys.exit(f"{own} is not set in ~/.archon/.env; wire the repo with new_project.py --alias {project}")


def main() -> None:
    import knowledge
    import status
    args = sys.argv[1:]

    def opt(name, default):
        return args[args.index(name) + 1] if name in args else default

    flags = {"--project", "--limit"}
    words = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in flags)]
    if not words:
        sys.exit(__doc__)
    env = status.read_env()
    project = opt("--project", "rasrs")
    var = token_var(project, env)
    k = knowledge.settings({"url": env.get("RASRS_URL", "${RASRS_URL}"),
                            "token": env.get(var, "${" + var + "}"), "project": project})
    result = knowledge.call_tool(k, "recall", {"project": k["project"], "query": " ".join(words),
                                              "limit": int(opt("--limit", "5"))})
    print(json.dumps(result, indent=1) if "--json" in args else render(result))


if __name__ == "__main__":
    main()
