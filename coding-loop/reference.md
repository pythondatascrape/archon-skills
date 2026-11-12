# Coding loop reference

## Pipeline

```text
docs/phase_docs/phase-XX.md --compile-phase-tasks--> docs/tasks/phase-XX.json (approved)
  --decompose-phase-subtasks--> docs/subtask/phase-XX/XX.NN.json   (run both directly; never plan-phase)
  --coding-loop--> branch phase/XX, per-sub-phase commits, PR opened at approval --> merge
```

Each step needs a clean, pushed base branch. Commit `docs/tasks/phase-XX.json` and `docs/subtask/phase-XX/` before the coding loop.

## Numbering

`01.04` (two digits) is a **sub-phase** (a file); `01.9` is a **task** inside one. Say
"sub-phase 01.04" and "task 01.9"; the user found the bare numbers confusing.

## Where things are

| What | Path |
|---|---|
| Workflow | `~/.archon/workflows/tasks/coding-loop/` (`coding-loop.yaml`, `scripts/`, `hooks/bash_guard.py`, `coder-skills.json`, `viz/`, `tests/`, `templates/python/`, `spec/`, `audit/`) |
| Tools (`coding-loop/tools/`) | `status.py` (what is it doing), `answer.py` (answer a gate), `stop.py` (stop a run gracefully), `resume_after_limit.py`, `learn.py` (every phase side by side), `plan_check.py` (plan wiring warnings), `skill_status.py` (each coder skill's current version on the skill server), `manual_ci.py` (the project's GitHub CI steps run here, result posted on the commit), `pyapi.py`, `compare_usage.py` |
| Shared controller | `~/.archon/workflows/tasks/.shared/loop_*.py`, plus `jev.py`, `knowledge.py`, `skill_fetch.py`, `usage_policy.json` |
| Coder scopes (while a coder runs) | `<project>/.coding-loop/coder-active` and `coder-scopes.json`; refusals in `guard-refusals.jsonl` |
| Skill cache | `~/.archon/skill-cache/` (coder skills from the skill server, checksum-verified) |
| Jev outcome ledger | `~/.archon/jev/workflow_jev.json` (`CODING_LOOP_JEV_LEDGER` overrides) |
| Phase state | `~/.archon/workspaces/_folder/<project>/state/coding-loop/phase-XX/` (`state.json`, `transitions.jsonl`, `metrics.jsonl`, `evidence/NNNN-*`, `exports/`, `baselines/`, `locks/`) |
| Run logs | `~/.archon/workspaces/_folder/<project>/logs/<run-id>.jsonl` |
| Run snapshots | `~/.archon/workspaces/_folder/<project>/workflow-source/runs/<run-id>/` |
| Project config | `<project>/.archon/coding-loop.json`: `phase_validation` (project checks), `suite_commands` (whole-suite commands left out of each task's gate; phase validation still runs them), `task_checks` (`changed_dir`/`new_file` commands at each task's GREEN), `skill_checks` (per skill, the check command a task routed to that skill runs in its gate; `{skill}` is the skill's folder, `{phase}` the phase; routes are in `coding-loop/coder-skills.json`, and a run refuses to start when a routed task's skill has none), `regenerate` (generated files the controller rewrites), `post_coder` (formatters run on the coder's changed files before its gate), `small_fix` (small edits outside a task's files allowed as P1 review findings; also decides which coders the guard holds strictly), `coder_models` / `test_models` (model per attempt), `blocking` (default `["P1","P2","P3"]`), `max_review_rounds` (default 5), `review_delta_medium_lines` (default 400), `security_scan`, `knowledge` (memory server), `jev`, `lsp`, `conventions`, `api_summary`, `mcp_servers`, `mcp_hint`, `max_parallel` (default 2). The README in the workflow folder explains each |
| Compiler config | `<project>/.archon/compile-phase-tasks.json`: `language`, `command_patterns`, ownership rules (`contract_globs`, `compatibility_file`, `companion_files` with `only_new`/`except`, `phase_outputs`, `contract_reader_globs`), `generator_commands`, `decision_globs`, `conventions` |
| Backups of the workflows | `~/.archon/backups/workflows-*.tgz` |

## States (TRANSITIONS table in loop_controller.py)

INITIALIZE -> PR_CREATED -> SUBTASK_SELECTED -> TEST_AUTHORING -> RED_VALIDATION ->
IMPLEMENTATION -> GREEN_VALIDATION -> ... -> PHASE_GREEN (all commands + project checks) ->
ADVERSARIAL_REVIEW <-> ADVERSARIAL_REMEDIATION -> ADVERSARIAL_PASSED -> SECURITY_REVIEW <->
SECURITY_REMEDIATION -> SECURITY_PASSED -> AWAITING_HUMAN_APPROVAL -> HUMAN_APPROVED -> COMMIT
-> PUSH -> PR_UPDATED -> [CI_CHECK ->] COMPLETE. Any state -> AWAITING_CLARIFICATION; failures -> STOPPED.

CI_CHECK runs only when the project has a GitHub CI file (`.github/workflows/*`, run on push or
pull_request). The `ci` node runs its `run` steps on a fresh copy of the PR's head on this machine
(`.shared/manual_ci.py`) and posts "manual-ci (<os>)" on the commit. Passed: COMPLETE. Failed:
STOPPED naming the step and its last lines; fix the branch, push, relaunch, and CI runs again on
the new head. A CI file it cannot run as written (GitHub `${{ }}` expressions, a non-bash shell)
completes with "CI not run" in the history, never a false pass. An `actions/checkout` step with a relative `path:` gets its own fresh copy of the commit at that path, for its job only; a checkout of another repository or a path it cannot reproduce counts as cannot run as written. A step whose `working-directory` does not exist fails at that step, naming the folder. By hand, from the project folder:
`python3 ~/.archon/workflows/tasks/coding-loop/tools/manual_ci.py [PR number|commit] [--no-post]`.

The same CI steps also run before approval, in SECURITY_PASSED once the reviews and project checks pass,
on a clean copy of the reviewed code (a commit made from the working tree that no branch points to;
nothing posted), so a git-ignored leftover in the project folder (an old build) cannot hide a failure.
Passed: approval. Failed: a P1 check finding for the failing step's command, fixed like a failing
project check; that command then runs with the project checks until it passes, and the clean run
repeats on the changed code. The loop chooses the tools for its checks instead of inheriting them: it asks
your login shell for the PATH a new terminal gets, picks the first install of each version the CI
file sets up (`actions/setup-node`, `actions/setup-python`: version, version file, or a simple
matrix), looking on that PATH and then the inherited one, and puts its folder first on the PATH of
every task command, project check and CI step. With no Node version asked for, it uses a new
terminal's Node. So a run does not depend on the PATH of whoever started or answered it. No install
of that version anywhere stops the run naming it ("asks for Node 24, but this machine's node is
v26.10.0 …"). Install it, check `node --version` in a new terminal, relaunch. A build that reports
the right version can still lack a feature (Homebrew's Node cannot build single-file programs):
keep it off a new terminal's PATH, or behind the build you want.

`PR_CREATED` keeps its name but only makes the branch: the PR opens at approval (PUSH ->
PR_UPDATED). Project checks (`phase_validation`, the full suite) run at the first PHASE_GREEN,
at a fresh one, and while a check finding is open; a review fix round's PHASE_GREEN runs the task
commands only. At SECURITY_PASSED they run once more when the tree changed since their last pass
(`full_validated`); a failure there opens a check finding and goes to ADVERSARIAL_REMEDIATION.
Blocking findings: P1-P3 in both reviews (project `blocking` can narrow it; P1 always blocks).
P4s are logged and, at approval, become ONE `follow-up` issue; deferred blocking findings become
ONE `hotfix` issue per phase (checklists). Each finding has 3 fix attempts, then the `stuck` gate.
A review that is still blocking after `max_review_rounds` (default 5) asks the owner. Each task
has 3 coding attempts; after the third the coder gate asks (an answer or amendment can fix it).
A failed prefetch does not count as one.

## Review rules decided by code

- A coder's DONE never closes a finding: it is RESOLVED only when the next review says so **and**
  the finding's file (or one the reviewer cites as the fix) changed. Open findings go back to the
  reviewer every round, with what it said is still missing (`last_review_evidence`).
- Findings outside the round's change become P4 notes from round 2 on; so do findings on
  conventions the gate already enforces, and a deferred known exception reported again on an
  unchanged file (same review, within 5 lines).
- Reviewers are read-only: any change a reviewer makes is undone.
- A proposed memory rule that is not one short claim is refused when kept.
- Left to the AI: severity, whether a requirement is unclear, whether a scanner hit is real, and
  whether a fix is complete. The record is `coding-loop/audit/prose-audit.md`.

## Models and tools

Coders: Opus on every attempt (`coder_models` cycles another order, e.g. `["opus","sonnet","opus"]`);
test writing starts on Sonnet and retries on Opus (`test_models`). Opus codes at high effort;
VALIDATION tasks, test-writing steps and prefetched work at medium. Project MCP servers come from
the config (a server that does not answer is dropped for that step, never fatal). Reviewers: Opus,
fresh, read-only (`Read, Grep, Glob, Bash`; no `Task`); security adds the getsentry
`security-review` skill and the project's `security_scan` results. Round 1 reviews run at high
effort; later rounds with a small change run on the `-medium` node. LSP: every coder and full
review node has an `-lsp` twin naming the LSP plugins; the step uses the twins only when every
plugin is installed (`"lsp": false` turns it off for a project).

## Coder guard

`hooks/bash_guard.py`, registered once in `~/.claude/settings.json` as a PreToolUse hook with matcher
`Bash|Read|Write|Edit|MultiEdit|NotebookEdit`. Without the full matcher the loop stops before any
coder starts and names the missing tools. It checks only the loop's coders (Archon's step label
`ARCHON_NODE_EXECUTION` names a `code-` step); any other session passes through. While a coder runs it refuses: context-flooding reads and
commands, Git changes, whole-suite test runs, any write outside the coder's working directory (a
prototype in /tmp), a write to a frozen file, and, for a strict coder, a write to a file not in its
permitted files. Strict: every test-writing step, and any coder the project's `small_fix` policy does
not cover. Shell writes (`>`, `tee`, `cp`, `mv`, `touch`, `sed -i`) are checked best-effort. Every
refusal is logged in `.coding-loop/guard-refusals.jsonl`. A coder that says "the hook blocked me" is
this guard; the fix is the plan (`files`), not the hook.

## Coder skills

`coding-loop/coder-skills.json` routes tasks to skills by task type or name pattern, and names each
skill by its `skill_id` on the skill server, never a version: skills are updated on the server and
live only there. At every launch the loop asks the server for each routed skill's active version,
fetches it unless a verified copy of that version is cached, checks every file's sha256 into
`~/.archon/skill-cache/`, and links `~/.claude/skills/<name>` to it; a project's own copy is never
used instead. The run records the version it used (`skill_versions` in state.json, and the
scorecard). It needs `SKILL_SERVER_URL` and `SKILL_SERVER_TOKEN` in `~/.archon/.env`. A server that
cannot be reached, a skill it does not know, or a routed skill without a `skill_checks` command
stops the run before it starts, naming the task; an older cached copy is never used in its place.
A skill update reaches the next launch (a relaunch too), never a running run.
`tools/skill_status.py` shows each skill's current version on the server.

## Parallel coding

While the current task is coded, one upcoming task (two with `"max_parallel": 3`) is coded at
medium effort in its own worktree (`code-p1`, `code-p2`; `prefetch` in state.json; `prefetch`,
`prefetch_used`, `prefetch_discarded` metrics) and gated on its turn without a model call. Only
dependency-ready, non-test-first tasks whose files overlap no unfinished earlier task or other
prefetch. `"max_parallel": 1` disables it. Overlapping files (a module file, a compatibility file)
serialize tasks, so the compiler's ownership rules also decide parallelism.

## Usage limits

`loop_ratelimit.py` asks Anthropic's usage endpoint (Claude Code login from the macOS
keychain), cached 60 s, and pauses before any model call at the thresholds in
`.shared/usage_policy.json` (5-hour window: 90 %, or `CODING_LOOP_PAUSE_AT`; 7-day: 100 %, paused
at the gate); it falls back to Archon's log records, labelled with their age. Disable with
`CODING_LOOP_USAGE_API=0`. A hold that `step`
sleeps through is `usage_hold` in state.json and shows as `PAUSED: usage limit (...), resumes ~HH:MM`
in status and the viewer (the Archon run still reads `running`; no model is called).

## Timeouts and killed nodes

Every script node sets `timeout:` (Archon's default is 120 s; `tests/test_workflow_timeouts.py`
guards all workflows). If a run fails with `exit 143` and no output, `status.py` prints
`RUN FAILED: node '<id>' was killed (exit 143) after N s`: raise that node's timeout, then
abandon and relaunch.

## Live viewer

`http://127.0.0.1:8765` (`viz/server.py`, page in `viz/page.html`, read per request). Start it
from a real terminal in the project: `nohup python3 ~/.archon/workflows/tasks/coding-loop/viz/server.py >/dev/null 2>&1 &`.
Page changes are verified by `tests/test_viz_render.py` (renders real payload variants in node).
For building viewers for other workflows, see the `archon-liveview` skill.
