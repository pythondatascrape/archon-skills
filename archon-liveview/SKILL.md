---
name: archon-liveview
description: "Build, run and fix live browser views for Archon workflows: a generic base viewer (~/.archon/workflows/tasks/.shared/liveview/base.py) that shows any workflow's runs, running nodes, model activity, gates and usage with zero setup, plus a small per-workflow adapter for workflow-specific panels. Use when the user wants to \"see\", \"watch\" or \"visualize\" a workflow as it runs, asks for a live page/dashboard/viewer for a workflow, or reports a viewer that is blank, stale or not updating. NOT for: the coding-loop's own viewer internals beyond its adapter (see the coding-loop skill) or publishing pages to claude.ai."
argument-hint: "[workflow-name] [build | run | fix]"
---

# Archon live views

**The rule: logic in the workflow folders, instructions here.** The base viewer is shared code
(`.shared/liveview/`); a workflow's adapter lives with that workflow (`<workflow>/viz/adapter.py`).

## Run a viewer (any workflow, no setup)

```bash
cd <project>   # any directory works; runs are found by workflow name across all workspaces
nohup python3 ~/.archon/workflows/tasks/.shared/liveview/base.py --workflow <name> \
  --port $(python3 -c "import json;print(json.load(open('$HOME/.archon/workflows/tasks/.shared/liveview/ports.json')).get('<name>',8770))") \
  [--adapter ~/.archon/workflows/tasks/<name>/viz/adapter.py] >/dev/null 2>&1 &
```

Ports are fixed per workflow in `.shared/liveview/ports.json` (coding-loop 8765 keeps its own
viewer). The user starts viewers from a **real terminal** when live usage is wanted: the usage
line reads the Claude Code login from the keychain, which Claude may not trigger. You may start
one for a demo with `CODING_LOOP_USAGE_API=0` (the page then labels usage as a stale record).

## Build an adapter for a new workflow

Read `building.md`. In short: find what the workflow writes (artifacts, state files, node
outputs), pick panels from the five types, write `panels(run) -> list[dict]` that only reads
and never raises, test it on a past run's real files, and render the page in node.

## Rules

`design-rules.md` holds the page rules learned on the coding-loop viewer (current run by
default, label every id's kind, targets vs results, keep scroll, stale data labelled, verify by
rendering). `operations.md` covers restarts and failure modes.
