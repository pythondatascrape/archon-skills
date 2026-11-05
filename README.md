# archon-skills

Claude Code skills for running Archon workflows, one folder per skill (each holds its `SKILL.md`).

| Skill | What it does |
|---|---|
| `archon-cli` | Drive Archon through its CLI: run, manage and author workflows |
| `archon-liveview` | Build and fix live browser views of Archon workflow runs |
| `coding-loop` | Operate and troubleshoot the coding-loop workflow |
| `coding-taskplan-loop` | Operate the task-plan fork of the coding loop |
| `rasrs` | Operate the rasrs project-memory server and its Archon wiring |
| `decision-record` | Create or check numbered decision records |
| `fingerprint-registry` | Check or update a registry of file fingerprints (sha256) |
| `phase-evidence-report` | Write or check a phase's evidence report |
| `requirement-traceability` | Map a phase's requirements to the tests that cover them |
| `schema-migration` | Create the next numbered migration or check numbering |

Install one skill: `cp -R <skill> ~/.claude/skills/`.

Tests (for the five skills with scripts): `uv run --with pytest pytest -q -p no:cacheprovider tests/<skill>`
