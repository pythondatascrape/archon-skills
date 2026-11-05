import json

from conftest import run


def dec(project, *args):
    return run("decision-record", "decision.py", *args, "--dir", "decisions", cwd=project)


def test_new_records_are_numbered_and_have_every_required_field(project):
    r = dec(project, "new", "--title", "Storage engine")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "decisions/D-01.json"
    rec = json.loads((project / "decisions" / "D-01.json").read_text())
    assert rec["id"] == "D-01" and rec["title"] == "Storage engine" and rec["status"] == "proposed"
    assert set(rec) >= {"decision", "rationale", "sources", "settles"}
    assert dec(project, "new", "--title", "Auth").stdout.strip() == "decisions/D-02.json"


def test_check_refuses_empty_fields_until_filled(project):
    dec(project, "new", "--title", "Storage engine")
    r = dec(project, "check")
    assert r.returncode == 1 and "D-01" in r.stdout and "decision" in r.stdout
    p = project / "decisions" / "D-01.json"
    rec = json.loads(p.read_text())
    rec.update(decision="SQLite", rationale="single file", sources=["docs/x.md"], status="resolved")
    p.write_text(json.dumps(rec))
    assert dec(project, "check").returncode == 0


def test_check_finds_a_mismatched_id_and_a_gap(project):
    (project / "decisions").mkdir()
    full = {"title": "t", "status": "resolved", "decision": "d", "rationale": "r", "sources": ["s"], "settles": []}
    (project / "decisions" / "D-01.json").write_text(json.dumps({"id": "D-01", **full}))
    (project / "decisions" / "D-03.json").write_text(json.dumps({"id": "D-02", **full}))
    r = dec(project, "check")
    assert r.returncode == 1 and "D-03.json" in r.stdout and "D-02" in r.stdout


def test_id_format_is_configurable(project):
    r = dec(project, "new", "--title", "x", "--id-format", "ADR-{n:03d}")
    assert r.stdout.strip() == "decisions/ADR-001.json"
