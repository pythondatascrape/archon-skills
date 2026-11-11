# rasrs reference

## Where things are

| What | Where |
|---|---|
| Program | `~/.local/bin/rasrs` (build: `CGO_ENABLED=0 go build -trimpath -o ~/.local/bin/rasrs ./cmd/rasrs` in `~/dev/rasrs`) |
| Data | `~/.local/share/rasrs/` |
| Server | launch agent `com.rasrs.serve` (`~/Library/LaunchAgents/com.rasrs.serve.plist`): `rasrs serve --http 127.0.0.1:8787` |
| Log | `~/Library/Logs/rasrs.log` |
| Address and tokens | `~/.archon/.env`: `RASRS_URL`, `RASRS_READ_TOKEN`, `RASRS_WRITE_TOKEN`, and per wired project `RASRS_<ALIAS>_READ_TOKEN` / `_WRITE_TOKEN` (mode 600) |
| Projects | one per wired repo; `status.py` lists each with its fact count, `rasrs --json project list` their IDs. The first is alias `rasrs` (name `rasrs-server`, shared tokens). The workflow repo itself is alias `archonloop` (name `archon-coding-loop`): the workflow's own decisions |
| Workflow code | `~/.archon/workflows/tasks/.shared/mcp_setup.py` (server entries), `knowledge.py` (client, claim rules), `loop_controller.py` `record_knowledge` (writer), `compile-phase-tasks/tools/seed_memory.py` (seeder) |
| Repo wiring | `.archon/coding-loop.json` (`mcp_servers.rasrs` with `roles`, `mcp_hint`, `review_mcp_hint`, `knowledge`) and `.archon/compile-phase-tasks.json` (`mcp_servers.rasrs`, `mcp_hint`) |

## Server control

```bash
launchctl bootout   gui/$(id -u)/com.rasrs.serve                                   # stop
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.rasrs.serve.plist      # start
launchctl kickstart -k gui/$(id -u)/com.rasrs.serve                                # restart
curl -s http://127.0.0.1:8787/livez                                                # ok
```

Restart Archon (no active run, no API key):

```bash
pkill -f "archon serve"; cd ~ && env -u ANTHROPIC_API_KEY nohup archon serve > ~/.archon/serve.log 2>&1 &
```

## Tokens

Each project has a read and a write token; `status.py` lists every token and its expiry.
- The first project's pair: `remote:archon_read` (`read`, every AI step) and `remote:archon_write`
  (`read,remember`, code only), in `RASRS_READ_TOKEN` / `RASRS_WRITE_TOKEN`; they expire about 2027-10-15.
- Each repo wired with `new_project.py` has its own pair, `remote:archon_read_<alias>` and
  `remote:archon_write_<alias>`, in `RASRS_<ALIAS>_READ_TOKEN` / `_WRITE_TOKEN`, valid a year from wiring.

Renew or replace, with the server stopped:

```bash
rasrs --json token create --principal remote:archon_read  --project <ID> --actions read            --expires-in 8760h
rasrs --json token create --principal remote:archon_write --project <ID> --actions read,remember   --expires-in 8760h
```

Things to know:
- **Principal:** must be `remote:NAME`, where NAME has no hyphens.
- **`--project`:** takes the project ID, not the alias; repeat it to cover several projects.
- **Max expiry:** 8760h.
- **Saving the token:** parse the token out of the JSON in code and replace the `.env` line in place, never echoing it.
- **Afterwards:** start the server, restart Archon, and remove the old tokens with `rasrs token revoke`.

## Seeding

```bash
cd <repo> && set -a && . ~/.archon/.env && set +a
python3 ~/.archon/workflows/tasks/compile-phase-tasks/tools/seed_memory.py . --dry-run   # what it would send
python3 ~/.archon/workflows/tasks/compile-phase-tasks/tools/seed_memory.py .
```

- **Sources:** every APPROVED `docs/tasks/phase-*.json` clarification. Each becomes claim = the answer, cut to the server's rule; rationale = the question plus the full answer; evidence = the task file at HEAD.
- **Amendments:** `docs/tasks/clarification-amendments.json`, if present, is recorded afterwards. Each amendment supersedes its original.
- **Reruns are safe:** identical claims come back as duplicates.
- **Amendment order:** an amendment whose original is not stored is skipped and reported, because a link cannot be added later.
- **Where it writes:** the `knowledge` entry of `.archon/coding-loop.json` names the server and the write token.

## Wiring a repo

Use `tools/new_project.py --repo REPO --alias ALIAS [--lang go] [--dry-run]` (2026-10-17). It
refuses while an Archon run is live, registers the project, gives it its **own** read and write
tokens (`remote:archon_read_<alias>`, `RASRS_<ALIAS>_READ_TOKEN`, …), so one project's coders
cannot read another's memory, writes a starter `.archon/` config for the language when missing, and
merges the wiring below into existing configs. Run `--dry-run` first, restart Archon afterwards,
then commit `.archon/` on a branch. The manual steps, for reference:

1. Stop the server. Run `rasrs project register --name NAME --alias ALIAS --path REPO --origin URL --default-branch main`. The name and alias must differ. Then make tokens that cover it (see Tokens) and start the server.
2. Edit the repo's `.archon/coding-loop.json`:
   - add `"rasrs": {"url": "${RASRS_URL}", "headers": {"Authorization": "Bearer ${RASRS_READ_TOKEN}"}, "roles": ["coder", "review"]}` under `mcp_servers`;
   - add `mcp_hint` and `review_mcp_hint`, naming the alias;
   - add `"knowledge": {"url": "${RASRS_URL}", "token": "${RASRS_WRITE_TOKEN}", "project": "ALIAS"}`.
3. Edit the repo's `.archon/compile-phase-tasks.json`: add the same server without `roles`, plus an `mcp_hint`.
4. Check with `status.py --repo REPO`. Never write a token into a repo file; status flags it.

### Automatic connection (2026-11-11)

The coding loop and compile-phase-tasks connect any repo that names no memory, at the first launch in
it: their preflight runs `new_project.py --repo R --alias <folder name> --no-repo-files --registry
--ignore-run <run id>`. That registers the project and its tokens and records the repo in the shared
list `~/.archon/memory-projects.json` (`MEMORY_PROJECTS_FILE`), which both workflows merge into the
repo's own settings (the repo's keys win). No repo file changes. That launch stops once: restart
Archon (no run active), then relaunch. `"knowledge": false` in `.archon/coding-loop.json` opts a repo out. The workflows find this tool through
`MEMORY_CONNECT` in `~/.archon/.env` (its full path); unset, a launch in an unconnected repo stops
and says so.

## Where it connects, and why

| Workflow | Step | Access | Why |
|---|---|---|---|
| compile-phase-tasks | interview (`ask`) | read | Finds settled decisions so it doesn't re-ask them, and surfaces pitfalls as questions |
| compile-phase-tasks | draft | none | The draft must follow from its inputs (the determinism contract) |
| decompose-phase-subtasks | (none) | none | It has no AI steps |
| coding-loop | coders | read | Recall before changing code |
| coding-loop | adversarial + security reviewers | read | Check the change against decisions |
| coding-loop | `record_knowledge` after the phase commit | write (code) | Records approved answers still in force, with the commit as evidence |

Why it's set up this way:
- **One shared server, not one per step.** `rasrs serve` holds one data lock, and coders run in parallel.
- **No secrets on disk.** Archon expands `$VAR`s in MCP `headers`/`env` (not in `url`; preflight expands the url) from its environment, which it loads from `~/.archon/.env` at start.
- **Reviewers still get MCP.** `allowed_tools` restricts only the built-in tools, not MCP tools.
- **Tool names.** Dotted names reach the model as `project_get` and so on.

## Server rules the code mirrors

- **Claim:** one line, at most 2 sentences (a run of `.!?` followed by whitespace or the end; `atom.go` and `v1.2` don't end one), no inline numbered list markers, at most 500 characters by default.
- **Rationale:** at most 2,000 characters.
- **Where these are set:** `knowledge.claim_from`; `claim_max`/`rationale_max` in the `knowledge` entry override them if the server's `text_limits` differ.
- **Write outcomes:** `supersedes_candidate` means "keep both" (acknowledged); recall then labels them as possibly conflicting. `rejected` raises an error.
- **Errors:** a failed call's reason is in the reply's text content, not its structured content.

## Moving to the Ubuntu laptop

The authoritative steps ship with rasrs: `rasrs help vps_setup`, `rasrs help cutover`, `rasrs help cutover_rollback`.

1. Install `rasrs` and `deploy/systemd/rasrs.service` on the laptop. It listens on 127.0.0.1:8787.
2. Put Tailscale (`tailscale serve`) or Caddy in front, and add that host name to `http_allowed_hosts`.
3. Cut over: backup and export here; on the laptop, `import --plan`, `import`, `reindex`, `parity`; then set this copy to `read_only: true`.
4. Create new tokens on the laptop. On this Mac, update `RASRS_URL=https://<host>/mcp` and the tokens in `~/.archon/.env`, then restart Archon. The repos don't change.
5. Once the laptop passes `status.py`, unload and delete the Mac's launch agent.

## History

- **2026-10-14:** set up.
- **First seed was discarded:** it stored amendments before their originals, so they weren't linked. That store is kept at `~/.local/share/rasrs.before-reset-2026-10-14` and is safe to delete.
- **Store sizes:** `status.py` shows each project's facts.
- **2026-11-05:** the workflow repo was registered as project `archonloop`. Its first 13 facts record the
  workflow changes of that week (prose audit gaps 1-5, the coder guard, the Jev ledger path, the skills
  repository, pinned coder skills, the change method), each with its merge commit as evidence. They were
  written once, at the owner's request; later workflow decisions are added the same way only when asked.
