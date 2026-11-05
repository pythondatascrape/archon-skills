"""new_project.py: wiring a new repo to Archon, the coding loop and rasrs (2026-10-17)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import new_project as np  # noqa: E402


def test_each_project_gets_its_own_principals_and_env_names():
    # One token for several projects would let one project's coders read another's memory.
    assert np.names("shopfront") == {
        "read_principal": "remote:archon_read_shopfront", "write_principal": "remote:archon_write_shopfront",
        "read_env": "RASRS_SHOPFRONT_READ_TOKEN", "write_env": "RASRS_SHOPFRONT_WRITE_TOKEN"}
    assert np.names("my-app")["read_principal"] == "remote:archon_read_my_app"  # no hyphens in principals
    assert np.names("my-app")["write_env"] == "RASRS_MY_APP_WRITE_TOKEN"


@pytest.mark.parametrize("alias", ["", "rasrs", "a b", "x" * 41, "-lead"])
def test_unusable_aliases_are_refused(alias):
    with pytest.raises(np.SetupError):
        np.check_alias(alias, taken={"rasrs"})


def test_env_lines_are_replaced_in_place_and_others_kept():
    text = "RASRS_URL=http://127.0.0.1:8787/mcp\nRASRS_X_READ_TOKEN=old\n# note\nOTHER=1\n"
    out = np.set_env(text, {"RASRS_X_READ_TOKEN": "new", "RASRS_X_WRITE_TOKEN": "w"})
    assert out == "RASRS_URL=http://127.0.0.1:8787/mcp\nRASRS_X_READ_TOKEN=new\n# note\nOTHER=1\nRASRS_X_WRITE_TOKEN=w\n"


def test_wiring_adds_rasrs_with_the_projects_own_tokens_and_keeps_the_rest():
    loop = {"phase_validation": ["make check"], "mcp_servers": {"gopls": {"command": "gopls", "args": ["mcp"]}},
            "mcp_hint": "Use gopls."}
    loop2, comp2 = np.wire(loop, {"contract_globs": ["c/*.json"]}, "shopfront")
    assert loop2["phase_validation"] == ["make check"] and loop2["mcp_servers"]["gopls"]["command"] == "gopls"
    srv = loop2["mcp_servers"]["rasrs"]
    assert srv == {"url": "${RASRS_URL}", "headers": {"Authorization": "Bearer ${RASRS_SHOPFRONT_READ_TOKEN}"},
                   "roles": ["coder", "review"]}
    assert loop2["knowledge"] == {"url": "${RASRS_URL}", "token": "${RASRS_SHOPFRONT_WRITE_TOKEN}",
                                  "project": "shopfront"}
    assert loop2["mcp_hint"].startswith("Use gopls.") and 'project "shopfront"' in loop2["mcp_hint"]
    assert 'project "shopfront"' in loop2["review_mcp_hint"]
    assert comp2["contract_globs"] == ["c/*.json"] and "roles" not in comp2["mcp_servers"]["rasrs"]
    assert 'project "shopfront"' in comp2["mcp_hint"]
    # wiring twice changes nothing
    assert np.wire(loop2, comp2, "shopfront") == (loop2, comp2)


def test_no_token_value_ever_lands_in_a_repo_config():
    loop, comp = np.wire({}, {}, "shopfront")
    text = json.dumps(loop) + json.dumps(comp)
    assert "Bearer ${" in text and not np.SECRET.search(text)


def test_go_starter_config_has_the_gates_and_no_project_specifics():
    cfg = np.starter("go")
    assert cfg["task_checks"]["changed_dir"]["command"] == "go test -count=1 ./{dir}/"
    assert "list" in cfg["task_checks"]["importers"]
    assert any("go vet ./..." in c for c in cfg["phase_validation"])
    assert any("go test" in g["deny"] for g in cfg["bash_guard"])
    text = json.dumps(cfg)
    assert "rasrs" not in text and "TestAC" not in text and "internal/" not in text


def test_python_starter_runs_the_suite_with_uv_and_guards_whole_runs():
    # A typical Python project: uv + pytest, tests in a flat tests/ directory.
    cfg = np.starter("python")
    assert cfg["phase_validation"] == ["uv run pytest -q"]
    assert cfg["plan_lint"] == {"test_filter_flag": "-k"}
    guard = cfg["bash_guard"][0]
    import re
    assert re.search(guard["deny"], "uv run pytest -q") and re.search(guard["deny"], "pytest")
    assert re.search(guard["unless"], "uv run pytest -q tests/test_settings.py")
    assert re.search(guard["unless"], "uv run pytest -q -k settings")
    assert re.search(guard["unless"], "uv run pytest -q | tail -n 60")
    assert not re.search(guard["unless"], "uv run pytest -q")


def test_other_languages_get_an_empty_starter():
    assert np.starter("rust") == {}


def test_an_alias_registered_to_another_repo_is_refused(tmp_path):
    project = {"aliases": ["demo"], "repository": {"path": "/elsewhere/demo"}}
    with pytest.raises(np.SetupError, match="registered to /elsewhere/demo"):
        np.check_same_repo(project, tmp_path)
    np.check_same_repo({"aliases": ["demo"], "repository": {"path": str(tmp_path)}}, tmp_path)


def test_starters_name_the_whole_suite_so_task_gates_leave_it_out():
    """The coding loop leaves suite_commands out of each task's gate and runs them once in phase
    validation; each one must also be a phase validation command so it still runs."""
    for lang, suite in (("go", "go test -count=1 ./..."), ("python", "uv run pytest -q")):
        cfg = np.starter(lang)
        assert cfg["suite_commands"] == [suite]
        assert set(cfg["suite_commands"]) <= set(cfg["phase_validation"])
