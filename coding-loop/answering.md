# Answering gates

## The reply forms (the controller parses them in code)

| Gate kind (status.py `clarification.kind`) | Reply |
|---|---|
| `coder` / `review` | decision **Answer**, every numbered question answered. `supersede ANS-NNN` replaces an earlier answer. Answers become tracked `ANS-` items reviewers must confirm COMPLIANT. |
| `coder` during a review fix (remediation active) | may start with `reroute 15.3, 15.5` to split the fix across tasks in phase order, each within its own files |
| `stuck` (a finding failed 3 fixes) | `reroute <tasks>` plus instructions (runs launched from 2026-10-10 show the text to the coder, track it as an ANS item, and honour `supersede ANS-NNN`; older runs used only the task ids), `defer: <reason>` (listed in the phase's one `hotfix` issue at approval; security P1 needs `defer-security: <reason>`), or `resolve: <reason>` when it is not a defect (a later answer changed the requirement); runs launched after 2026-10-11 only |
| `owner` (no task permits the file) | exactly one task id |
| `red_command` | the exact RED command(s), one per line |
| approval | `approve` (commits and pushes exactly the reviewed tree) or `reject` naming task ids `01.13: ...` |

The user replies in Archon's web console by choosing **Answer** (or Approve/Reject). Its
generic **Continue** sends decision `approved` with the text: the controller takes that as the
answer at a question and as approval at the approval gate, where the console shows no separate
Approve button (user decision 2026-10-08; coleam00/Archon#3953). From a terminal:
`tools/answer.py <project> --phase XX --file reply.txt [--amended]` checks and sends it, then
reports ACCEPTED or NOT ACCEPTED.

## Decide the answer in this order

1. **Read the code and the task contracts**, not just the question: owners
   (`docs/subtask/phase-XX/*.json` `files`/`frozen`), the actual types and fields, the rule
   ids the question cites (`docs/tasks/phase-XX.json` rules, `CLAR-` answers).
2. **Is there an in-scope way?** Coders often ask for a file because of their own test design
   (01.1: wanted to edit a fixture; a direct test of the real file in its own test did the job).
3. **Do other tasks own the files?** During remediation: `reroute <tasks>`.
4. **Does no task own them?** That is a *plan gap*: amend the plan while the run is paused
   (add the paths to the task's `files` in `docs/subtask/phase-XX/<sub>.json`), **confirm the
   edit is on disk, and only then tell the user "answer now"**. The controller accepts an
   amendment only when the answer arrives; one that lands after it is reverted at the coder's
   next step (2026-10-08: lost by 16 s; a copy is now kept and status shows it).
   `answer.py --amended` refuses to send until the edit is saved.
   The controller validates the amendment, records it, and commits it with the phase.
   Examples: 01.13 needed `internal/policy/policy_test.go`, the generated dependency graph and
   `contracts/compatibility.json`; 15.5's ADV-003 needed `internal/storage/migrations.go`.
5. **Is it a real defect nobody can fix in this phase?** `defer:` with the reason.

## Patterns seen

- **Plan gaps the compiler now catches** (a Go project's `.archon/compile-phase-tasks.json`, 2026-10-08): a
  new CLI command without `internal/cli/cli.go`, `serve.go` without `internal/mcp/server.go`, a
  new storage file without `contracts/boundaries_test.go`, a migration without
  `internal/storage/migrations_test.go`, a generator as a validation command. In a phase compiled
  before these rules, expect them and amend.
- **A contract change drags in more files.** When an answer adds a schema field or details key,
  amend in the same step: the schema's fixtures, the test that pins its keys (for example
  `auditDetailsFields` in `contracts/audit_test.go`), `contracts/compatibility.json`, and
  `contracts/generated/dependency-graph.mmd` when a new package import follows. Phase 02 needed
  two extra pauses for these.
- **"Comes from contract X" needs the generator.** Before answering that a value must come from a
  contract, check the generated code has it (C7: `internal/policy/policy_gen.go`); if not, the
  task also owns `tools/contractgen/main.go` and the generated files.
- **An older phase's test fails at the last task.** A regression from an earlier task in the
  phase (task checks now catch most at that task). Give the asking task the test file, and fix the
  test to pin what it means (C13), not the production code.
- **Agent-reachable actions** (security gate): refuse for a restricted agent, no caller-supplied
  paths beyond the working directory, identical refusals (C11).
- **A decision source nobody enforces** (an accepted D-record's `sources` key): enforce it in this
  phase on every entry point, with limit / limit+1 / configured / default tests.
- **Other tasks' pending RED tests break repo-wide commands** (`go vet ./...`): the controller
  excuses failures whose only files are pending RED tests of later tasks; the coder must not
  implement other tasks' code.
- **Contract files and their hash**: editing a file listed in `contracts/compatibility.json`
  requires updating only that file's sha256 (version 1 unfrozen until task 06.31).
- **JSON output without a contract**: use an existing schema when it matches; never invent
  response fields; record a P4 follow-up for a later contract phase.
- **Security reviewer "unstated requirements"**: state them concretely (modes 0600/0700,
  create-then-fill to avoid a window, do not chmod a user's own directory) and require tests.
- **A test-first step whose tests already pass** (phase 11, 11.14): when an answer turns an
  IMPLEMENTATION task into a pin of existing behavior, its test-first split can never go RED.
  Amend the task's `task_type` to `VALIDATION` (`expected_gate` stays GREEN) and answer
  `--amended`. After the answer, the controller drops the RED split for a validation task, and the
  coder returns DONE without changing anything. Never tell the coder to assert something false to
  get RED.
- **A change breaks a dependent package's test** (phase 11, 11.10 → 11.13): `task_checks` run
  only the changed directory, so an `internal/mcp` change that breaks an `internal/cli` test
  surfaces at a later task's whole-suite command. Give that later task the test file. Fix where the
  test reads from, not the decided behavior.
- **Check every rule in a schema, not only its enums,** before claiming an item is already
  resolved (phase 11 ADV-029: `busy` is in the state enum, but `allOf` allows it only with
  status `ok`).

Write the answer as a fenced block ready to paste, then a two-line plain-language summary.

## Approval review

Do not trust the package alone:

1. `status.py --phase XX`: state `AWAITING_HUMAN_APPROVAL`, HEAD and branch as recorded.
2. The tree on disk equals the reviewed tree (both reviews' `reviewed` ids == `git write-tree`
   of the working tree via a temp index; the controller's `loop_exec.write_tree`).
3. Run every task command and every project check **fresh** on that tree, and confirm the run
   left the tree unchanged.
4. Check each stated goal in the code (for a hotfix: every issue, file by file).
5. P1-P3 block, so approval shows only P4s (follow-ups for when the application is complete).
   Read each; if a later phase builds on one (owners in later `docs/subtask/` files, contract
   freeze tasks), it is really a P3: reject naming its owner task so it is fixed now.
6. Before merging a PR that should close issues, check GitHub links them
   (`closingIssuesReferences`); add `Closes #N` lines if not.

Verdict first ("approve" / "reject 01.x: ..."), then the evidence table.
