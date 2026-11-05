"""Tests for the rasrs skill's tools: what status reports as a problem (and the fix it names),
the repo wiring check, and recall's output. Raw facts are gathered separately (collect) so
these run without a server.

Run:  uv run --with pytest pytest -q -p no:cacheprovider ~/.claude/skills/rasrs/tests
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import recall  # noqa: E402
import status  # noqa: E402

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


def healthy():
    return {
        "server": {"livez": True, "launchd": True},
        "env": {"file_mode": "600", "vars": {"RASRS_URL": "http://127.0.0.1:8787/mcp", "RASRS_READ_TOKEN": 43,
                                             "RASRS_WRITE_TOKEN": 43},
                "mtime": NOW - timedelta(hours=2)},
        "archon": {"started": NOW - timedelta(hours=1)},
        "auth": {"RASRS_READ_TOKEN": "ok", "RASRS_WRITE_TOKEN": "ok"},
        "tokens": [{"principal": "remote:archon_read", "expires_at": (NOW + timedelta(days=300)).isoformat()},
                   {"principal": "remote:archon_write", "expires_at": (NOW + timedelta(days=300)).isoformat()}],
        "stats": {"index": {"state": "healthy"}, "projects": [{"name": "p", "atoms": 3}]},
    }


def fixes(facts):
    return {p["problem"]: p["fix"] for p in status.problems(facts, NOW)}


def test_a_healthy_setup_has_no_problems():
    assert status.problems(healthy(), NOW) == []


@pytest.mark.parametrize("change, problem, fix", [
    (lambda f: f["server"].update(livez=False), "server is not answering", "launchctl bootstrap"),
    (lambda f: f["server"].update(livez=False, launchd=False), "server is not loaded", "launchctl bootstrap"),
    (lambda f: f["env"]["vars"].pop("RASRS_READ_TOKEN"), "RASRS_READ_TOKEN is not set", "~/.archon/.env"),
    (lambda f: f["env"].update(file_mode="644"), "readable by others", "chmod 600"),
    (lambda f: f["env"].update(mtime=NOW), "changed after Archon started", "restart Archon"),
    (lambda f: f["auth"].update(RASRS_WRITE_TOKEN="HTTP 401"), "RASRS_WRITE_TOKEN is refused", "token create"),
    (lambda f: f["tokens"][0].update(expires_at=(NOW + timedelta(days=10)).isoformat()), "expires in 10 days",
     "token create"),
    (lambda f: f["stats"]["index"].update(state="degraded"), "index is degraded", "rasrs reindex"),
])
def test_each_problem_names_its_fix(change, problem, fix):
    f = healthy()
    change(f)
    found = fixes(f)
    hit = [p for p in found if problem in p]
    assert hit, found
    assert fix in found[hit[0]]


def test_when_the_server_is_down_auth_is_not_blamed():
    f = healthy()
    f["server"]["livez"] = False
    f["auth"] = {"RASRS_READ_TOKEN": "unreachable", "RASRS_WRITE_TOKEN": "unreachable"}
    assert not any("refused" in p for p in fixes(f))


def write_cfg(root, loop=None, compile_=None):
    (root / ".archon").mkdir(parents=True, exist_ok=True)
    if loop is not None:
        (root / ".archon/coding-loop.json").write_text(json.dumps(loop))
    if compile_ is not None:
        (root / ".archon/compile-phase-tasks.json").write_text(json.dumps(compile_))


SERVER = {"url": "${RASRS_URL}", "headers": {"Authorization": "Bearer ${RASRS_READ_TOKEN}"}, "roles": ["coder", "review"]}


def test_wiring_of_a_fully_connected_repo(tmp_path):
    write_cfg(tmp_path, {"mcp_servers": {"rasrs": SERVER}, "knowledge": {"url": "${RASRS_URL}",
              "token": "${RASRS_WRITE_TOKEN}", "project": "rasrs"}},
              {"mcp_servers": {"rasrs": {k: v for k, v in SERVER.items() if k != "roles"}}})
    w = status.wiring(tmp_path)
    assert w == {"coders": True, "reviewers": True, "writer": "rasrs", "interview": True, "problems": [],
                 "token_vars": ["RASRS_READ_TOKEN", "RASRS_WRITE_TOKEN"]}


def test_a_projects_own_token_names_are_checked_like_the_shared_ones(tmp_path):
    # new_project.py gives each project its own tokens (RASRS_<ALIAS>_READ_TOKEN, ...).
    own = {**SERVER, "headers": {"Authorization": "Bearer ${RASRS_DEMO_READ_TOKEN}"}}
    write_cfg(tmp_path, {"mcp_servers": {"rasrs": own}, "knowledge": {"url": "${RASRS_URL}",
              "token": "${RASRS_DEMO_WRITE_TOKEN}", "project": "demo"}})
    assert status.wiring(tmp_path)["token_vars"] == ["RASRS_DEMO_READ_TOKEN", "RASRS_DEMO_WRITE_TOKEN"]
    f = healthy()
    f["repo"] = {"problems": [], "recorded": [], "token_vars": ["RASRS_DEMO_READ_TOKEN", "RASRS_DEMO_WRITE_TOKEN"]}
    assert any("RASRS_DEMO_READ_TOKEN is not set" in p for p in fixes(f))
    f["env"]["vars"].update({"RASRS_DEMO_READ_TOKEN": 40, "RASRS_DEMO_WRITE_TOKEN": 40})
    assert not any("RASRS_DEMO" in p for p in fixes(f))


def test_wiring_flags_a_secret_written_into_the_repo(tmp_path):
    leaked = {**SERVER, "headers": {"Authorization": "Bearer rsk_abcdefghijklmnopqrstuvwxyz0123"}}
    write_cfg(tmp_path, {"mcp_servers": {"rasrs": leaked}})
    assert any("secret" in p for p in status.wiring(tmp_path)["problems"])


def test_wiring_of_an_unconnected_repo(tmp_path):
    w = status.wiring(tmp_path)
    assert w["coders"] is False and w["writer"] is None and w["interview"] is False


def test_recall_output_shows_status_conflicts_and_evidence():
    """The shape the server returns: id, claim, status, conflict, conflicts_with, evidence, rationale."""
    result = {"results": [{"id": "a1", "claim": "Backups live in backup.env.", "status": "active", "conflict": True,
                           "conflicts_with": ["a9"], "rationale": "CLAR-07-004 amended", "score": 0.9,
                           "evidence": [{"type": "design_record", "path": "docs/tasks/phase-07.json"}]}]}
    text = recall.render(result)
    assert "Backups live in backup.env." in text and "[active]" in text and "a1" in text
    assert "docs/tasks/phase-07.json" in text and "may conflict with a9" in text
    assert recall.render({"results": []}) == "No facts found."


def test_recall_uses_the_projects_own_read_token():
    """A repo wired by new_project.py has RASRS_<ALIAS>_READ_TOKEN; the shared token cannot see it."""
    env = {"RASRS_READ_TOKEN": "shared", "RASRS_SHOPFRONT_READ_TOKEN": "own", "RASRS_MY_APP_READ_TOKEN": "app"}
    assert recall.token_var("shopfront", env) == "RASRS_SHOPFRONT_READ_TOKEN"
    assert recall.token_var("my-app", env) == "RASRS_MY_APP_READ_TOKEN"


def test_recall_keeps_the_shared_token_for_rasrs():
    assert recall.token_var("rasrs", {"RASRS_READ_TOKEN": "shared"}) == "RASRS_READ_TOKEN"


def test_recall_names_the_missing_project_token_instead_of_borrowing_another():
    with pytest.raises(SystemExit) as exc:
        recall.token_var("other", {"RASRS_READ_TOKEN": "shared"})
    assert "RASRS_OTHER_READ_TOKEN" in str(exc.value) and "new_project.py" in str(exc.value)
