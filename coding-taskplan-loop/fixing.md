# Fixing the controller during a phase

The controller is `~/.archon/workflows/tasks/coding-taskplan-loop/lib/loop_controller.py` (with `loop_core`,
`loop_exec`, `loop_ratelimit`, `loop_approval`, `loop_export`); node scripts are in
`coding-taskplan-loop/scripts/`. Tests: `coding-taskplan-loop/tests/` (~110) plus `archon workflow test` fixtures.

## The snapshot rule

Archon copies the whole workflow tree, its `lib/` included, into
`~/.archon/workspaces/<kind>/<project>/workflow-source/runs/<run-id>/` at launch, and that run
executes only its copy. So:

- A fix never reaches a paused or running run. The user must **abandon and relaunch**
  (`archon workflow abandon <id>`, then launch the phase again). Say this before they answer.
- The viewer (`coding-taskplan-loop/viz/server.py`) is a separate process: its page (`viz/page.html`)
  reloads from disk per request; `server.py` or `lib/` changes need a viewer restart. The
  viewer reads the keychain for live usage, so the user restarts it (in a real terminal).

## How a relaunch resumes

`preflight` -> `resume_if_stopped()`: a STOPPED phase resumes in the state it stopped in, with
a fresh attempt budget (`attempts_before_resume` keeps the count for the record). A resume in
`RED/GREEN_VALIDATION` re-runs the gate under the current rules on the work in the tree
(`revalidate`): pass -> certified; fail -> a fresh coding attempt with that evidence.
A phase paused at a question (not stopped) comes back to the same question.

## Workflow for a fix (every step, every time)

1. Reproduce from evidence: `status.py`, the evidence folder named in the transition, the run
   log `~/.archon/workspaces/.../logs/<run>.jsonl`.
2. Back up the file you change (`cp` to the scratchpad) so you can prove fail-before.
3. Write the fix, then a test that **fails on the old code and passes on the new**: swap the
   backup in, run the test, swap back. A test that passes on both proves nothing (it happened:
   identical command output never looked "changed").
4. Full suite: `cd ~/.archon/workflows/tasks/coding-taskplan-loop && uv run --with pytest pytest -q -p no:cacheprovider tests/`
   and `cd <project> && archon workflow test`; `archon workflow list --json` shows load errors.
5. **Dry-run the resume on copies** before telling the user to relaunch:

```bash
S=<scratchpad>/dry; rm -rf $S; mkdir -p $S/state/coding-taskplan-loop $S/art
cp -R <project> $S/repo
cp -R ~/.archon/workspaces/_folder/<project>/state/coding-taskplan-loop/phase-XX $S/state/coding-taskplan-loop/
python3 - "$S" <<'EOF'   # repoint the baseline store at the copy
import json, os, sys; S = sys.argv[1]; st = f"{S}/state/coding-taskplan-loop/phase-XX/state.json"; s = json.load(open(st))
real = os.path.expanduser("~/.archon/workspaces/_folder/<project>/state")
if s.get("baseline"): s["baseline"]["store"] = s["baseline"]["store"].replace(real, f"{S}/state")
json.dump(s, open(st, "w"))
EOF
cd $S/repo && python3 -I - "$S" <<'EOF'
import sys, os; sys.path.insert(0, os.path.expanduser('~/.archon/workflows/tasks/coding-taskplan-loop/lib'))
from pathlib import Path; from loop_controller import Controller
S = Path(sys.argv[1]); c = Controller(Path.cwd(), "XX", S/"state", S/"art", "dry-run")
print(c.resume_if_stopped()); c.revalidate()        # or c.commit(), c.absorb_answer({...}) ...
print(c.s["state"], c.s["stopped"], c.s["history"][-1]["reason"])
EOF
```

   Only then tell the user to relaunch, quoting what the dry run showed.
6. Clean `__pycache__` under `~/.archon/workflows/tasks` (captured into run snapshots otherwise).

## Fixes made on 2026-10-07 (know them before re-fixing)

Excuse failures only in other tasks' pending RED tests; resume from validation states;
plan amendments during a pause (validated, recorded, baseline adopts them, committed);
related commands writing their owners' files are not the fixer's violation; amended plan
files authorized at commit; attempts survive a resume; live usage from Anthropic's usage
endpoint with stale-labelled log fallback.

## Fixes made on 2026-10-08 (after phase 02; backup `workflows-before-groupA-20261008-152059.tgz`)

- `_names_tests` (loop_core): a test directory counts as a RED command only as a whole argument
  with a trailing slash (`dir/`, `./dir/...`), never inside another value or as bare `./dir`
  (`go build`/`go run` name it without running tests). Checked old vs new on every phase run so far.
- `task_checks` (`changed_dir`, `new_file`) run at every non-RED task gate.
- `Controller.revert(paths, why)` is the only restore: every revert logged; plan files copied to
  `evidence/NNNN-plan-reverted/` and listed in `reverted_plan_edits`.
- INITIALIZE makes only the branch; `update_pr` creates the PR at approval after
  `open_hotfix_issues` / `open_followup_issues` (one issue per kind per phase, `phase_issue`).
- `mark_usage_hold` / `clear_usage_hold` around `rl.hold(on_wait=)`; status and viewer say PAUSED.
- Gate messages: `ANSWER_HEAD` / `APPROVAL_HEAD`; `shown_before` adds the no-decision note;
  `CONTINUE_DECISIONS` (`approved`/`approve`/`continue`) with text = the answer at a question.
- Review prompts: name the contract change and the tests pinning it when a fix needs one.
- Every script node has `timeout:`; `status.py` `killed_node()` reports exit 143/137.
- Compiler (`phase_contract.py`): `companion_files` `only_new`/`except`/literal `when`,
  `generator_commands`, `decision_globs`, `conventions` in `context.json`.
- Round 2 (from the phase 02 transition log): `regenerate` rules + `generated_files()` exempt
  from all scope checks; `route_models(task, attempt, order)` with `coder_models`; a failed
  prefetch (`prefetch_try`) does not count as an attempt; compile/interview prompts require the
  API that test-first tasks call. Prefetch loss on relaunch was the 10-07 slot naming, already fixed.
- 2026-10-08 (after phase 16): `split_plan` returns None when every permitted file is one of the task's own test files (16.5 / ADV-001; would also have hit 06.4, 06.27, 06.29, 07.24, 08.27). Continue at the approval gate approves (user decision). Pending-RED excuse also by failing test name (`excused_by_tests`).
