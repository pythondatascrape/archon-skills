# Building an adapter

1. **What does the workflow leave behind?** `ls ~/.archon/workspaces/*/<project>/artifacts/runs/<run-id>/`
   for a past run, its node scripts' outputs (`output_format` fields), any state it keeps
   (`STATE_DIR`), and its run log `logs/<run-id>.jsonl`. The adapter may read only these.
2. **Pick panels** (rendered by the base page; no per-workflow HTML or JS):

| type | fields | use for |
|---|---|---|
| `steps` | `steps: [..]`, `current` | where the run is in its node path |
| `kv` | `items: [[label, value], ..]` | counts and identities |
| `table` | `columns`, `rows` | tasks, findings, files |
| `card` | `body` (plain text) | a single message or result |
| `feed` | `items: [{ts?, text}]` | a report or log excerpt (scroll position is kept) |

3. **Write `<workflow>/viz/adapter.py`** from `templates/adapter.py`: `panels(run)` gets
   `{id, workspace, origin, started, log, status, paused, nodes, events}`. Read files with
   existence checks; a half-finished run must give fewer panels, never an exception (the base
   page shows "Adapter error" instead of blanking, but treat that as a bug).
4. **Label every id with its kind** in titles and labels ("sub-phase 01.04", "task 01.9", "run 2f38…").
5. **Test**: call `panels()` on a real past run (read-only), then start the viewer on its port
   and render `/api/state` with `node ~/.archon/workflows/tasks/.shared/liveview/tests/render_harness.js
   <page.html> <payload.json>`. A green syntax check is not enough.

Worked example: `~/.archon/workflows/tasks/decompose-phase-subtasks/viz/adapter.py`.
