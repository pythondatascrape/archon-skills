"""Live-view adapter for decompose-phase-subtasks (also the worked example for new adapters).

    python3 ~/.archon/workflows/tasks/.shared/liveview/base.py --workflow decompose-phase-subtasks \
        --adapter ~/.archon/workflows/tasks/decompose-phase-subtasks/viz/adapter.py

panels(run) reads only what the run wrote: its artifacts folder (manifest.json, report.md) and
the node progress the base viewer already parsed. It never writes and never raises on a
half-written run: missing files simply mean fewer panels.
"""

import json
from pathlib import Path

STEPS = ["plan", "write", "route", "review", "finalize"]


def panels(run: dict) -> list[dict]:
    art = Path(run["workspace"]) / "artifacts" / "runs" / run["id"]
    out = []
    running = [n["step"] for n in run.get("nodes", [])]
    if run.get("paused"):
        current = "review"
    elif running:
        current = running[0]
    else:
        current = "finalize" if run.get("status") == "completed" else None
    out.append({"type": "steps", "title": "Path (current node highlighted)", "steps": STEPS, "current": current})
    manifest = art / "manifest.json"
    if manifest.is_file():
        m = json.loads(manifest.read_text())
        out.append({"type": "kv", "title": f"Phase {m.get('phase', '?')}", "items": [
            ["sub-phase files", len(m.get("files", {}))], ["pairs (TEST+IMPL)", len(m.get("pairs", []))],
            ["unpaired (cycle)", len(m.get("unpaired", []))], ["output", m.get("output_dir", "")]]})
        if m.get("pairs"):
            out.append({"type": "table", "title": "Paired tasks", "columns": ["test task", "implementation task"],
                        "rows": [[t, i] for t, i in m["pairs"]]})
    report = art / "report.md"
    if report.is_file():
        lines = [l for l in report.read_text().splitlines() if l.strip()]
        out.append({"type": "feed", "title": "Decomposition report", "items": [{"text": l} for l in lines[:80]]})
    return out
