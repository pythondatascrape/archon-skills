# phase-evidence-report: Markdown reports (2026-11-06)

Phase plans may name the evidence report `docs/evidence/phase-NN.md`. The script wrote JSON whatever
the name, and `check` crashed (JSONDecodeError) on a Markdown report. Now a report path ending in `.md`
is written as readable Markdown (commit, machine, versions, checks, owner facts, acceptance criteria
with their requirements and tests) with the data `check` reads at the end in an HTML comment; any
other path is JSON as before. `check` reads either, and a missing or hand-written report is refused
with the command to run, never a crash.

Locked test: `tests/phase-evidence-report/test_evidence_markdown.py`. RED: 3 failed on the old code
(Markdown output, two crashes); 3 passed already and pin behaviour that stays.

Checked on a copy of a finished phase: the hand-written report is refused with what to run; build
wrote a Markdown report with 15 acceptance criteria and check passed.
