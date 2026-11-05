"""seed_code.py: the backfill CLI over the coding loop's .shared/code_links (requested 2026-10-19).
What the facts hold is tested in coding-loop tests/test_code_links.py; these test the CLI.


For every task of every docs/subtask/phase-XX/*.json plan whose sub-phase commit is on the
current branch, seed_code records:
- one fact per rule: claim = rule id, task and value; evidence = the plan file, the rule's
  subject file (with each top-level function or class the rule text names, by line range), and
  every test that covers the rule (by name and line range); files, symbols, tags and the
  sub-phase commit are set so recall can filter on them;
- one fact per task: its files, tests and rules;
- one code-map fact per src module at HEAD: its docstring and public names with line ranges.
  A rerun supersedes the module's earlier code-map fact when the map changed.
--dry-run sends nothing.

Run:  uv run --with pytest pytest -q -p no:cacheprovider ~/.claude/skills/rasrs/tests
"""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import seed_code  # noqa: E402
import code_links  # noqa: E402

MODULE = '''"""Search eligible skills.

Second paragraph is not part of the map."""


def search_skills(conn, principal, query, *, settings):
    return []


def catalog_generation(conn):
    return 0


def _private(conn):
    return 1


class SearchError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
'''

TESTS = '''def test_search_refuses_long_query():
    assert True


def test_generation_changes():
    assert True
'''

PLAN = {
    "subphase_id": "04.05",
    "tasks": [{
        "task_id": "04.5",
        "task_name": "Implement search",
        "files": ["src/pkg/search.py", "tests/test_search.py", "testdata/x/*.json"],
        "rules": [
            {"id": "04.5-R1", "subject": "src/pkg/search.py", "property": "query_limit",
             "value": "search_skills refuses a query over 512 characters with SearchError invalid_request",
             "source": "CLAR-04-002", "quote": "512 characters"},
            {"id": "04.5-R2", "subject": "src/pkg/search.py", "property": "generation",
             "value": "catalog_generation(conn) changes on every lifecycle change",
             "source": "clarification answer", "quote": "generation"},
        ],
        "tests": [
            {"name": "test_search_refuses_long_query", "file": "tests/test_search.py", "class": "NEGATIVE",
             "covers": ["04.5-R1"]},
            {"name": "test_generation_changes", "file": "tests/test_search.py", "class": "POSITIVE",
             "covers": ["04.5-R2"]},
            {"name": "test_not_written_yet", "file": "tests/test_search.py", "class": "POSITIVE",
             "covers": ["04.5-R2"]},
        ],
    }],
}


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src/pkg").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "docs/subtask/phase-04").mkdir(parents=True)
    (r / "docs/subtask/phase-05").mkdir(parents=True)
    (r / "src/pkg/search.py").write_text(MODULE)
    (r / "src/pkg/__init__.py").write_text("")
    (r / "tests/test_search.py").write_text(TESTS)
    (r / "docs/subtask/phase-04/04.05.json").write_text(json.dumps(PLAN))
    later = json.loads(json.dumps(PLAN))
    later["subphase_id"], later["tasks"][0]["task_id"] = "05.01", "05.1"
    (r / "docs/subtask/phase-05/05.01.json").write_text(json.dumps(later))
    git(r, "init", "-q")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m",
        "Phase 04 sub-phase 04.05: 04.5 Implement search")
    return r


def by_kind(facts, kind):
    return [f for f in facts if kind in f["tags"]]


@pytest.fixture
def memory():
    calls, existing = [], []
    state = {"disposition": "created"}
    out = {"calls": calls, "existing": existing, "state": state}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name, args = body["params"]["name"], body["params"]["arguments"]
            calls.append((name, args))
            if name == "recall":
                res = {"results": existing}
            else:
                res = {"disposition": state["disposition"], "persisted": True, "atom_id": f"atom-{len(calls)}"}
            data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": res, "content": []}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out["url"] = f"http://127.0.0.1:{srv.server_port}/mcp"
    yield out
    srv.shutdown()


def wire(repo, url):
    (repo / ".archon").mkdir()
    (repo / ".archon/coding-loop.json").write_text(json.dumps(
        {"knowledge": {"url": url, "token": "${SEED_TEST_TOKEN}", "project": "proj"}}))


def run_tool(repo, *extra):
    tool = Path(seed_code.__file__)
    out = subprocess.run([sys.executable, str(tool), str(repo), "--source", "src/pkg", *extra],
                         capture_output=True, text=True, env={"SEED_TEST_TOKEN": "t", "PATH": "/usr/bin:/bin",
                                                               "HOME": str(Path.home())})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_dry_run_sends_nothing(repo, memory):
    wire(repo, memory["url"])
    report = run_tool(repo, "--dry-run")
    assert report["would_record"] == {"rule": 2, "task": 1, "code-map": 1}
    assert memory["calls"] == []


def test_write_records_every_fact_with_commit_symbols_and_files(repo, memory):
    wire(repo, memory["url"])
    report = run_tool(repo)
    assert report == {"recorded": 4, "unchanged": 0, "superseded": 0, "errors": []}
    sent = [a for n, a in memory["calls"] if n == "remember"]
    assert len(sent) == 4 and all(a["project"] == "proj" for a in sent)
    rule = sent[0]
    assert rule["commit_sha"] == git(repo, "rev-parse", "HEAD")
    assert rule["symbols"] and rule["files"] and rule["evidence"]


def test_rerun_supersedes_a_changed_code_map(repo, memory):
    wire(repo, memory["url"])
    memory["existing"].append({"id": "old-map", "status": "active", "claim": "src/pkg/search.py: older map",
                               "tags": ["code-map", "module:search"]})
    report = run_tool(repo)
    assert report["superseded"] == 1
    maps = [a for n, a in memory["calls"] if n == "remember" and "code-map" in a["tags"]]
    assert maps[0]["links"] == [{"to": "old-map", "relation": "supersedes"}]
    recalls = [a for n, a in memory["calls"] if n == "recall" and "code-map" in a["filters"]["tags"]]
    assert recalls[0]["filters"] == {"tags": ["code-map"], "files": ["src/pkg/search.py"], "status": ["active"]}


def test_rerun_counts_duplicates_as_unchanged(repo, memory):
    wire(repo, memory["url"])
    memory["state"]["disposition"] = "duplicate"
    report = run_tool(repo)
    assert report["recorded"] == 0 and report["unchanged"] == 4


def test_default_source_is_the_src_package_or_a_go_module_root(repo, tmp_path):
    # 2026-10-29: a Go repo has no src/; its packages live under internal/ and cmd/ below go.mod.
    assert seed_code.default_source(repo) == "src/pkg"
    (repo / "go.mod").write_text("module example.com/demo\n")
    assert seed_code.default_source(repo) == "src/pkg"  # src/ still wins
    gorepo = tmp_path / "gorepo"
    (gorepo / "internal/search").mkdir(parents=True)
    assert seed_code.default_source(gorepo) is None
    (gorepo / "go.mod").write_text("module example.com/demo\n")
    assert seed_code.default_source(gorepo) == "."
