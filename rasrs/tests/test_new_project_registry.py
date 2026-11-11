"""new_project.py for the workflows' automatic connection (2026-11-11): the shared list of
connected repos, no repo files, and the calling run left out of the live-run check."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import new_project as np  # noqa: E402


def test_a_registry_entry_holds_only_the_rasrs_settings_for_both_workflows():
    entry = np.registry_entry("shopfront")
    loop, comp = np.wire({}, {}, "shopfront")
    assert entry == {"alias": "shopfront", "coding-loop": loop, "compile-phase-tasks": comp}
    # no starter gates, so a repo in any language keeps its own (or the loop's default) gates
    assert set(entry["coding-loop"]) == {"mcp_servers", "mcp_hint", "review_mcp_hint", "knowledge"}
    assert set(entry["compile-phase-tasks"]) == {"mcp_servers", "mcp_hint"}
    assert not np.SECRET.search(json.dumps(entry))


def test_recording_a_repo_keeps_the_others_and_is_private(tmp_path):
    reg = tmp_path / "memory-projects.json"
    reg.write_text(json.dumps({"projects": {"/r/one": np.registry_entry("one")}}))
    np.record_registry(reg, Path("/r/two"), "two")
    doc = json.loads(reg.read_text())
    assert set(doc["projects"]) == {"/r/one", "/r/two"}
    assert doc["projects"]["/r/two"]["alias"] == "two"
    assert stat.S_IMODE(os.stat(reg).st_mode) == 0o600
    np.record_registry(reg, Path("/r/two"), "two")  # again: unchanged
    assert json.loads(reg.read_text()) == doc


def test_a_missing_registry_is_created(tmp_path):
    reg = tmp_path / "sub" / "memory-projects.json"
    np.record_registry(reg, Path("/r/x"), "x")
    assert json.loads(reg.read_text())["projects"]["/r/x"]["alias"] == "x"


def test_the_registry_path_can_be_moved_for_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_PROJECTS_FILE", str(tmp_path / "r.json"))
    assert np.registry_path() == tmp_path / "r.json"
    monkeypatch.delenv("MEMORY_PROJECTS_FILE")
    assert np.registry_path() == Path.home() / ".archon" / "memory-projects.json"


def test_the_calling_run_is_not_counted_as_live(monkeypatch):
    out = ("Recent runs (3 of 3):\n\n"
           "  4a99f5aa  running  coding-loop · active node(s): preflight  (5s)\n"
           "  28a3ea07  paused   coding-loop · active node(s): controller.human  (2h)\n"
           "  19fead97  cancelled  coding-loop  (1d)\n")
    monkeypatch.setattr(np, "_run", lambda *a, **k: type("P", (), {"stdout": out})())
    assert len(np._live_runs()) == 2
    live = np._live_runs(ignore="4a99f5aa-35a4-47c6-a86a-c1d5cb8b5762")
    assert len(live) == 1 and "28a3ea07" in live[0]


def test_the_command_line_offers_the_new_options():
    src = (Path(__file__).resolve().parents[1] / "tools" / "new_project.py").read_text()
    for flag in ("--no-repo-files", "--registry", "--ignore-run"):
        assert flag in src
