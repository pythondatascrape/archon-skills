---
name: decision-record
description: Create the next numbered decision record (all required fields present) or check that every record is complete, correctly numbered and has no gaps. Use for any "define decision record" or ADR task.
---

- New: `python3 ${CLAUDE_SKILL_DIR}/scripts/decision.py new --title "<title>" --dir <records folder> [--id-format D-{n:02d}]`. It prints the path; fill in decision, rationale, sources and settles.
- Check: `python3 ${CLAUDE_SKILL_DIR}/scripts/decision.py check --dir <records folder> [--id-format ...] [--required id,title,...]`. Exit 1 lists each problem.
- If the project fingerprints its records, run the fingerprint-registry skill afterwards.
