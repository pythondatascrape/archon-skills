---
name: rasrs
description: "Operate the user's rasrs memory server and its connection to the Archon workflows: check it is up and wired, look facts up (recall, read-only), explain what a workflow step recalled or the coding loop recorded, renew tokens, seed decisions, add a repo, restart things, troubleshoot, and move the server to the Ubuntu laptop. Use when the user mentions rasrs, project memory, recall/remember, \"what does memory say about X\", tokens, the memory server, seeding, or RASRS_* variables. NOT for: changing rasrs's own code (that is the coding loop's phase work), or connecting Claude Code itself (the user keeps Claude Code advisory)."
argument-hint: "[status | recall <query> | tokens | seed | add-repo | move | fix]"
---

# rasrs: operate project memory

rasrs is the user's long-term project memory: short facts, each with evidence (a file, a commit,
a decision). It runs on this Mac as a launch agent at `http://127.0.0.1:8787/mcp` and serves the
Archon workflows. Claude Code is **not** connected to it, and stays advisory: you use the tools
below, read-only.

## Always start here

```bash
python3 ~/.claude/skills/rasrs/tools/status.py --repo <repo>      # add --json for everything
```

One read-only call. It reports:
- server up and loaded at login;
- `~/.archon/.env` complete, private, and loaded by the running Archon;
- both tokens authenticating, and their expiry;
- what the store holds and the search index state;
- how the repo is wired;
- what the coding loop last recorded.

Every problem comes with its fix. Read it before saying anything about rasrs.

To answer "what does memory say about X":

```bash
python3 ~/.claude/skills/rasrs/tools/recall.py "<query>" [--project <alias>] [--limit N]
```

Explain **in plain language first** (what is true, what it means, what the user does next), then
the detail.

## Rules that prevent real failures

1. **Never print or send a token.** They live only in `~/.archon/.env`. Read them in code, never
   echo them; when writing them, replace in place and show `<redacted>`.
2. **Memory is a hint, never authority.** A recalled fact is checked against the file its
   evidence points to before anyone relies on it.
3. **No AI writes.** AI steps hold the read-only token. Only the coding loop's code writes
   (approved answers, after the phase commit) and `seed_memory.py`. Never call `remember` yourself
   unless the user asks for that specific fact.
4. **Stop the server before commands that take the data lock** (`token create`/`revoke`,
   `project register`, `import`, `restore`, `parity`, `reindex`), then start it again. `stats`,
   `health`, `token list` and `backup` work while it runs.
5. **Restart Archon only when no run is active** (`archon workflow status --all --json` shows
   none), and only without `ANTHROPIC_API_KEY`: the user runs on the Claude subscription.
6. **A stored fact cannot be edited or re-linked.** Getting it wrong means a new fact that
   supersedes it, or (only for a store holding nothing but seeded data, with the user's OK)
   a reset and a re-seed. Dry-run before any bulk write (`seed_memory.py --dry-run`).
7. **Workflow code changes follow the coding-loop skill's rules:** tests first, project-agnostic,
   never during a live run, then install from this repository into `~/.archon/workflows/tasks/`.

## Route by situation

| Situation | Do |
|---|---|
| "Is it working?" / anything odd | `status.py --repo <repo>`, then its fixes |
| "What does memory say about …" | `recall.py`; cite the evidence paths |
| A run stopped: "…uses RASRS_READ_TOKEN, which is not set", or compile cancelled "memory server … unusable" | `status.py`: usually `.env` changed after Archon started, so restart Archon |
| Recording failed: the coding-loop phase notes say "knowledge not recorded" or "errors" | The run is fine. Start the server; facts from that run's answers are in its state (`status.py` shows them). Re-seed only covers answers in `docs/tasks` |
| Tokens expiring or refused | reference.md › Tokens |
| Seed or re-seed decisions | reference.md › Seeding |
| Link memory to the code (rules → functions → tests, module maps), after each phase merge | `tools/seed_code.py <repo> --dry-run`, then without it; reruns write only what changed |
| Connect another repo | `tools/new_project.py --repo R --alias A --dry-run`, then without `--dry-run` (reference.md › Wiring a repo) |
| Move to the Ubuntu laptop | reference.md › Moving |

The user's own plain-language guide is `~/Desktop/rasrs_usage.md`. Keep it in step when
something it describes changes. The Write tool cannot write to ~/Desktop: write the file in the
scratchpad and `cp` it there.
