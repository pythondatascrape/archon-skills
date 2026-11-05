---
name: requirement-traceability
description: Map every requirement in a phase plan to the tests that cover it and check each test exists in its file. Use for any "requirement traceability", "traceability registry" or "validate requirements" task.
---

`python3 ${CLAUDE_SKILL_DIR}/scripts/trace.py --plan <phase plan JSON> [--pattern <id regex>] [--out <trace JSON>]`

- Exit 0: every requirement has a test, and every test was found.
- Exit 1: one line per problem (a requirement with no test, or a test not found in its file), naming the tasks to fix.
- `--out` writes {"requirements": {id: ["file::test"]}, "problems": [...]} for the project's registry.
