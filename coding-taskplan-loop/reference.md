# Coding loop reference

## Pipeline

```text
docs/phase_docs/phase-XX.md --compile-phase-tasks--> docs/tasks/phase-XX.json (approved)
  --decompose-phase-subtasks--> docs/subtask/phase-XX/XX.NN.json   (run both directly; never plan-phase)
  --coding-taskplan-loop--> branch phase/XX, per-sub-phase commits, PR opened at approval --> merge
```

Each step needs a clean, pushed base branch. Commit `docs/tasks/phase-XX.json` and `docs/subtask/phase-XX/` before the coding loop.

## Numbering

`01.04` (two digits) is a **sub-phase** (a file); `01.9` is a **task** inside one. Say
"sub-phase 01.04" and "task 01.9"; the user found the bare numbers confusing.

## Where things are

| What | Path |
|---|---|
| Workflow | `~/.archon/workflows/tasks/coding-taskplan-loop/` (`coding-taskplan-loop.yaml`, `scripts/`, `tools/` (`status.py`, `answer.py`, `resume_after_limit.py`), `viz/`, `tests/`, `templates/python/`) |
| Controller (the fork's own copy) | `~/.archon/workflows/tasks/coding-taskplan-loop/lib/loop_*.py` |
| Phase state | `~/.archon/workspaces/_folder/<project>/state/coding-taskplan-loop/phase-XX/` (`state.json`, `transitions.jsonl`, `metrics.jsonl`, `evidence/NNNN-*`, `exports/`, `baselines/`, `locks/`) |
| Run logs | `~/.archon/workspaces/_folder/<project>/logs/<run-id>.jsonl` |
| Run snapshots | `~/.archon/workspaces/_folder/<project>/workflow-source/runs/<run-id>/` |
| Project config | `<project>/.archon/coding-taskplan-loop.json`: `phase_validation` (project checks), `task_checks` (`changed_dir`/`new_file` commands at each task's GREEN), `regenerate` (generated files the controller rewrites), `coder_models` (model per attempt), `conventions`, `api_summary`, `mcp_servers`, `mcp_hint`, `max_parallel` |
| Compiler config | `<project>/.archon/compile-phase-tasks.json`: `language`, `command_patterns`, ownership rules (`contract_globs`, `compatibility_file`, `companion_files` with `only_new`/`except`, `phase_outputs`, `contract_reader_globs`), `generator_commands`, `decision_globs`, `conventions` |
| Backups of the workflows | `~/.archon/backups/workflows-*.tgz` |

## States (TRANSITIONS table in loop_controller.py)

INITIALIZE -> PR_CREATED -> SUBTASK_SELECTED -> TEST_AUTHORING -> RED_VALIDATION ->
IMPLEMENTATION -> GREEN_VALIDATION -> ... -> PHASE_GREEN (all commands + project checks) ->
ADVERSARIAL_REVIEW <-> ADVERSARIAL_REMEDIATION -> ADVERSARIAL_PASSED -> SECURITY_REVIEW <->
SECURITY_REMEDIATION -> SECURITY_PASSED -> AWAITING_HUMAN_APPROVAL -> HUMAN_APPROVED -> COMMIT
-> PUSH -> PR_UPDATED -> COMPLETE. Any state -> AWAITING_CLARIFICATION; failures -> STOPPED.

`PR_CREATED` keeps its name but only makes the branch: the PR opens at approval (PUSH ->
PR_UPDATED). Blocking findings: adversarial P1/P2, security P1. At approval the open P3s become
ONE `follow-up` issue and deferred blocking findings ONE `hotfix` issue per phase (checklists). Each finding has 3 fix attempts, then
the `stuck` gate. Each task has 3 coding attempts (default Opus, Sonnet, Opus; `coder_models` overrides it); a failed prefetch does not count as one.

## Models and tools

Coders: Opus (high effort) first, Sonnet on failure; project MCP servers from the config; the
`LSP` tool from user-scope plugins (`gopls-lsp`, `pyright-lsp`). Reviewers: Opus, read-only
(`Read, Grep, Glob, Bash, LSP`; security adds `Task` and the getsentry `security-review` skill).

## Parallel coding

Up to two upcoming, file-disjoint, dependency-ready tasks are coded ahead in worktrees
(`prefetch` in state.json; `prefetch`, `prefetch_used`, `prefetch_discarded` metrics) and gated
on their turn without a model call. `max_parallel` in `.archon/coding-taskplan-loop.json` (1 disables).
Measured potential on phase 01: task coding 94 -> ~50 min. Overlapping files (go.mod,
compatibility.json) serialize tasks, so the compiler's ownership rules also decide parallelism.

## Usage limits

`loop_ratelimit.py` asks Anthropic's usage endpoint (Claude Code login from the macOS
keychain), cached 60 s, and pauses the loop at 90 % of any window; it falls back to Archon's
log records, labelled with their age. Disable with `CODING_LOOP_USAGE_API=0`. A hold that `step`
sleeps through is `usage_hold` in state.json and shows as `PAUSED: usage limit (...), resumes ~HH:MM`
in status and the viewer (the Archon run still reads `running`; no model is called).

## Timeouts and killed nodes

Every script node sets `timeout:` (Archon's default is 120 s; `tests/test_workflow_timeouts.py`
guards all workflows). If a run fails with `exit 143` and no output, `status.py` prints
`RUN FAILED: node '<id>' was killed (exit 143) after N s`: raise that node's timeout, then
abandon and relaunch.

## Live viewer

`http://127.0.0.1:8769` (`viz/server.py`, page in `viz/page.html`, read per request). Start it
from a real terminal in the project: `nohup python3 ~/.archon/workflows/tasks/coding-taskplan-loop/viz/server.py >/dev/null 2>&1 &`.
Page changes are verified by `tests/test_viz_render.py` (renders real payload variants in node).
For building viewers for other workflows, see the `archon-liveview` skill.
