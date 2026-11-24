"""supersede_facts.py: replace wrong facts from an owner-approved list (fix_fuckup Part 5, 2026-11-24).

Practice pass first (sends no remember), each correcting fact supersedes its old fact, evidence must
exist at the revision, and nothing is written while any fact has a problem.

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
TOOL = Path(__file__).resolve().parents[1] / "tools" / "supersede_facts.py"
sys.path.insert(0, str(TOOL.parent))
import supersede_facts  # noqa: E402

OLD = "01a1fe56-0527-740e-8ac2-f5d09db83014"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    git(r, "remote", "add", "origin", "https://github.com/acme/widget-dev.git")
    (r / "src/old.ts").write_text("x\n")
    (r / "src/check.ts").write_text("".join(f"line {i}\n" for i in range(1, 11)))
    git(r, "add", "-A")
    git(r, "commit", "-qm", "one")
    (r / "src/old.ts").unlink()
    git(r, "add", "-A")
    git(r, "commit", "-qm", "remove old")
    return r


@pytest.fixture
def memory():
    calls, state = [], {"facts": [{"id": OLD, "status": "active"}], "found_by": None, "written": False}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            name, args = body["params"]["name"], body["params"]["arguments"]
            calls.append((name, args))
            if name == "recall":
                if state["written"] and args.get("include_history"):
                    res = {"results": [{"id": OLD, "status": "superseded"}, {"id": "new-1", "status": "active"}]}
                elif state["written"]:
                    res = {"results": [{"id": "new-1", "status": "active"}]}
                elif state["found_by"] in (None, args["query"]):
                    res = {"results": state["facts"]}
                else:
                    res = {"results": []}  # a long query crowded out by the size budget
            else:
                state["written"] = True
                res = {"disposition": "created", "persisted": True, "atom_id": "new-1"}
            data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": res, "content": []}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"calls": calls, "state": state, "url": f"http://127.0.0.1:{srv.server_port}/mcp"}
    srv.shutdown()


def approved(tmp_path, repo, replacement, old_claim="01.1-R1: <project-id>=<owner>/<repo>"):
    p = tmp_path / "approved.json"
    p.write_text(json.dumps({"project": "widget-dev", "repo": str(repo), "revision": "main",
                             "approved": "owner, 2026-11-24",
                             "facts": [{"id": OLD, "old_claim": old_claim, "why": "removed",
                                        "replacement": replacement}]}))
    return p


def run(path, url, *extra, tmp_path):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "RASRS_URL": url,  # set values win over ~/.archon/.env
           "RASRS_WIDGET_DEV_READ_TOKEN": "r", "RASRS_WIDGET_DEV_WRITE_TOKEN": "w"}
    out = subprocess.run([sys.executable, str(TOOL), str(path), *extra], capture_output=True, text=True, env=env)
    return out.returncode, json.loads(out.stdout.strip().splitlines()[-1]), out


GOOD = "Since phase 06 there is no entry format; src/old.ts was removed. Evidence: src/check.ts:2-3, :9."


def test_practice_pass_sends_no_remember_and_shows_the_plan(tmp_path, repo, memory):
    plan_md = tmp_path / "plan.md"
    code, rep, _ = run(approved(tmp_path, repo, GOOD), memory["url"], "--plan-out", str(plan_md), tmp_path=tmp_path)
    assert code == 0 and rep["practice"] and rep["with_problems"] == 0
    assert all(name == "recall" for name, _ in memory["calls"])
    text = plan_md.read_text()
    assert OLD in text and "Nothing was written" in text and "src/check.ts:2-3" in text and "src/check.ts:9" in text


def test_write_supersedes_the_old_fact_with_evidence_and_checks_recall(tmp_path, repo, memory):
    code, rep, out = run(approved(tmp_path, repo, GOOD), memory["url"], "--write", tmp_path=tmp_path)
    assert code == 0, out.stderr
    rem = [a for n, a in memory["calls"] if n == "remember"]
    assert len(rem) == 1
    a = rem[0]
    assert a["links"] == [{"to": OLD, "relation": "supersedes"}]
    assert a["claim"] == " ".join(GOOD.split())
    assert {"type": "source", "path": "src/check.ts", "line_start": 2, "line_end": 3} .items() <= a["evidence"][0].items()
    assert all(e.get("path") != "src/old.ts" for e in a["evidence"])  # named as removed: not evidence
    assert OLD in a["rationale"] and "superseded-fact" in a["tags"]
    assert rep["written"] == 1 and rep["recall"] == [{"old": OLD, "new": "new-1", "new_first": True,
                                                      "old_status": "superseded"}]


def test_missing_file_or_line_is_a_problem_and_nothing_is_written(tmp_path, repo, memory):
    bad = "Since phase 06 the rule moved. Evidence: src/nowhere.ts:1, src/check.ts:40."
    code, rep, _ = run(approved(tmp_path, repo, bad), memory["url"], "--write", tmp_path=tmp_path)
    assert code == 1 and rep["written"] == 0
    probs = " ".join(rep["problems"][OLD])
    assert "src/nowhere.ts does not exist" in probs and "src/check.ts:40 is outside the file" in probs
    assert not [n for n, _ in memory["calls"] if n == "remember"]


def test_old_fact_missing_or_already_replaced_is_a_problem(tmp_path, repo, memory):
    memory["state"]["facts"] = []
    code, rep, _ = run(approved(tmp_path, repo, GOOD), memory["url"], tmp_path=tmp_path)
    assert code == 1 and "old fact not found" in " ".join(rep["problems"][OLD])
    memory["state"]["facts"] = [{"id": OLD, "status": "superseded"}]
    code, rep, _ = run(approved(tmp_path, repo, GOOD), memory["url"], tmp_path=tmp_path)
    assert code == 1 and "already superseded" in " ".join(rep["problems"][OLD])


def test_old_fact_is_found_by_its_label_when_the_whole_claim_misses(tmp_path, repo, memory):
    memory["state"]["found_by"] = "01.1-R1"
    code, rep, _ = run(approved(tmp_path, repo, GOOD), memory["url"], tmp_path=tmp_path)
    assert code == 0 and rep["with_problems"] == 0


def test_a_bare_file_name_from_another_repository_is_not_evidence(repo):
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ev, _, problems = supersede_facts.evidence_of("Only tests or standard-extensions.json; src/check.ts:1.", repo, sha, None)
    assert not problems and [e["path"] for e in ev] == ["src/check.ts"]


def test_same_wording_as_the_old_fact_is_a_problem(tmp_path, repo, memory):
    same = "The rule is in src/check.ts:1."
    code, rep, _ = run(approved(tmp_path, repo, same, old_claim=same), memory["url"], tmp_path=tmp_path)
    assert code == 1 and "repeat" in " ".join(rep["problems"][OLD])


def test_too_long_claim_loses_only_its_evidence_sentence():
    text = "One. Two. Evidence: src/a.ts:1."
    claim, problem = supersede_facts.fit_claim(text)
    assert claim == "One. Two." and problem is None
    claim, problem = supersede_facts.fit_claim("One. Two. Three. Evidence: src/a.ts:1.")
    assert problem and "2 sentences" in problem


def test_pull_request_and_commit_become_evidence(repo):
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ev, _, problems = supersede_facts.evidence_of(f"Moved by PR #26 (commit {sha[:7]}).", repo, sha, "acme/widget-dev")
    assert not problems
    assert {"type": "issue", "reference": "https://github.com/acme/widget-dev/pull/26"} in ev
    assert {"type": "commit", "revision": sha} in ev
