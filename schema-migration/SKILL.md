---
name: schema-migration
description: Create the next numbered database migration file or check that migration numbering has no gaps, duplicates or misnamed files. Use for any "migrate to", "add migration" or schema change task before writing the migration's SQL.
---

- New: `python3 ${CLAUDE_SKILL_DIR}/scripts/migration.py new "<name>" --dir <migrations folder> [--format {n:04d}_{slug}.sql]`. It prints the new file's path; write the migration there.
- Check: `python3 ${CLAUDE_SKILL_DIR}/scripts/migration.py check --dir <migrations folder> [--format ...]`. Exit 1 lists each problem.
