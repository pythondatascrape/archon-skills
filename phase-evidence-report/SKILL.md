---
name: phase-evidence-report
description: Write or check a phase's evidence report (commit, tool versions, settings, machine, test and audit results, owner-supplied facts, and acceptance criteria mapped to their requirements and tests from the phase plan). Use for any "gate evidence report", "phase evidence" or end-of-phase evidence task instead of writing the report by hand.
---

1. If the project has no config yet, create one (JSON); every key is optional and `{phase}` is replaced:
   `plan`, `report`, `versions` ({name: command}), `result_command`, `advisory_command`,
   `static` ({section: object}), `owner_inputs` ({"file", "required": [keys]}), `acceptance_pattern`.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/evidence.py build --phase NN --config <config>`
   - Exit 2: it lists every owner fact still missing and the file to put them in. Ask the owner for all of them in one question.
   - Exit 1: the result or advisory command failed; the report records it.
3. `python3 ${CLAUDE_SKILL_DIR}/scripts/evidence.py check --phase NN --config <config>`: every test the report names exists, and the commands passed.
