---
name: coding-loop
description: "Operate and troubleshoot the Archon coding-loop workflow (~/.archon/workflows/tasks/coding-loop): diagnose a phase run, explain what it is doing, help answer its clarification and approval gates, review an approval package, and fix the controller safely. Use when the user says \"why did it stop\", \"what is it doing\", \"it stopped again\", pastes a \"CLARIFICATION NEEDED - PHASE xx\" message, asks to review an approval file, or mentions the coding loop, a phase run, sub-phases, tasks like 01.9, findings like ADV-003, or the live viewer. NOT for: authoring new workflows (archon-cli skill) or writing phase documents."
argument-hint: "[status | answer | approve | fix] [project] [phase]"
---

# Coding loop: operate, answer, fix

The coding loop executes one phase of approved sub-phase documents
(`docs/subtask/phase-XX/*.json`) through a code-only state machine: test-first RED, GREEN,
adversarial and security review, remediation, human approval, per-sub-phase commits, PR.
**Gates and decisions are code, never prose.** The user decides at the gates; you help them
decide. Never answer a gate, approve, relaunch or abandon a run on your own initiative.

## Always start here

```bash
python3 ~/.archon/workflows/tasks/coding-loop/tools/status.py <project> [--phase XX] [--json]
```

One read-only call: run id + status/outcome, controller state, task and sub-phase, a stop
reason or the open question in full, the last transitions, the failing evidence tail,
findings/answer counts and plan amendments. Read it before saying anything about a run.

Then explain **in plain language first** (what happened, what it means, what the user does
next), and only then the technical detail. The user asks "plain language?" when you skip this.

## Route by situation

| Situation | Read |
|---|---|
| A `CLARIFICATION NEEDED` message, or the user asks how to answer | `answering.md` |
| The run stopped, or behaves wrongly, or a controller fix is needed | `fixing.md` |
| Reviewing an approval file or the approval package | `answering.md` → *Approval review* |
| Paths, states, files, project config, the coder guard, skill pins, the live viewer | `reference.md` |

## Six rules that prevented real failures

1. **Permitted files are enforced in code**, twice: the coder guard refuses a write as it happens
   (`reference.md` → *Coder guard*), and the gate reverts what slips through. "Yes, you may edit X"
   does nothing if X is not in the task's `files`. Find the in-scope way first, then `reroute`,
   then a plan amendment.
2. **A running or paused run uses a snapshot of the workflow** taken at launch
   (`workflow-source/runs/<id>/`). A controller fix reaches only a *relaunch*. Say so up front.
3. **Before telling the user to relaunch after a fix, dry-run the resume on a COPY** of the
   repo and the phase state (`fixing.md` has the recipe). Two relaunches failed on 2026-10-07
   because this was skipped.
4. **`reroute` reads every task id in the answer text.** Mention only the tasks you route to.
5. **Amend first, then say "answer now".** The controller reads a plan amendment only when the
   answer arrives; check the edit is on disk before the user answers (or use `answer.py --amended`).
6. **Verify before claiming.** Run the checks fresh on the exact tree; read the actual code for
   type and field names; test page changes by rendering them, not by syntax checks.
