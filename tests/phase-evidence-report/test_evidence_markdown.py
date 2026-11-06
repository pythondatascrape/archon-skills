"""A Markdown evidence report (2026-11-06): plans may name the report `….md`. build writes readable
Markdown with the same facts and, at the end, the data the check reads; check reads either format and
never crashes on a report it cannot read (a hand-written report names what to run instead)."""
import json

from conftest import run

CFG = {"plan": "plans/phase-{phase}.json", "report": "docs/evidence/phase-{phase}.md", "result_command": "true"}


def setup(project, cfg=CFG):
    (project / "skill.json").write_text(json.dumps(cfg))


def ev(project, action):
    return run("phase-evidence-report", "evidence.py", action, "--phase", "03", "--config", "skill.json", cwd=project)


def test_build_writes_a_readable_markdown_report(project):
    setup(project)
    r = ev(project, "build")
    assert r.returncode == 0, r.stderr
    text = (project / "docs/evidence/phase-03.md").read_text()
    assert text.startswith("# Phase 03 evidence")
    assert "AC-03-001" in text and "tests/test_a.py::test_alpha" in text and "03.1, 03.2" in text
    assert "| result | `true` | passed |" in text


def test_check_reads_the_markdown_report_it_built(project):
    setup(project)
    ev(project, "build")
    r = ev(project, "check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_on_markdown_finds_a_missing_test(project):
    setup(project)
    ev(project, "build")
    (project / "tests" / "test_a.py").write_text("def test_other():\n    assert True\n")
    r = ev(project, "check")
    assert r.returncode == 1 and "AC-03-001: tests/test_a.py::test_alpha not found" in r.stdout


def test_a_hand_written_report_is_refused_with_what_to_run_not_a_crash(project):
    setup(project)
    (project / "docs/evidence").mkdir(parents=True)
    (project / "docs/evidence/phase-03.md").write_text("# Phase 03 evidence\n\nAll good.\n")
    r = ev(project, "check")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert "evidence.py build" in r.stdout


def test_a_missing_report_is_refused_not_a_crash(project):
    setup(project)
    r = ev(project, "check")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "docs/evidence/phase-03.md" in r.stdout


def test_a_json_report_still_works(project):
    setup(project, {**CFG, "report": "evidence/phase-{phase}.json"})
    assert ev(project, "build").returncode == 0
    assert json.loads((project / "evidence/phase-03.json").read_text())["phase"] == "03"
    assert ev(project, "check").returncode == 0
