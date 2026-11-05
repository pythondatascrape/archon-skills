import json
import sys

from conftest import run

CFG = {"plan": "plans/phase-{phase}.json", "report": "evidence/phase-{phase}.json",
       "versions": {"python": f"{sys.executable} --version"},
       "result_command": "true", "advisory_command": "echo no known vulnerabilities",
       "static": {"configuration": {"test_command": "pytest -q"}},
       "owner_inputs": {"file": "evidence/phase-{phase}.owner.json", "required": ["latency_p95_ms", "manual_restore"]}}


def setup(project, cfg=CFG, owner=None):
    (project / "evidence").mkdir(exist_ok=True)
    (project / "skill.json").write_text(json.dumps(cfg))
    if owner is not None:
        (project / "evidence" / "phase-03.owner.json").write_text(json.dumps(owner))


def build(project):
    return run("phase-evidence-report", "evidence.py", "build", "--phase", "03", "--config", "skill.json", cwd=project)


def test_build_writes_the_report_from_the_plan_and_the_run(project):
    setup(project, owner={"latency_p95_ms": 41, "manual_restore": "passed 2026-10-27"})
    r = build(project)
    assert r.returncode == 0, r.stderr
    rep = json.loads((project / "evidence" / "phase-03.json").read_text())
    assert len(rep["commit"]) == 40 and rep["phase"] == "03"
    assert rep["versions"]["python"].startswith("Python 3")
    assert rep["result"] == {"command": "true", "outcome": "passed", "exit_code": 0}
    assert rep["advisory"]["outcome"] == "passed" and "no known" in rep["advisory"]["output"]
    assert rep["configuration"] == {"test_command": "pytest -q"}
    assert rep["hardware"]["machine"] and rep["hardware"]["system"]
    assert rep["owner"] == {"latency_p95_ms": 41, "manual_restore": "passed 2026-10-27"}
    ac = {a["id"]: a for a in rep["acceptance_criteria"]}
    assert ac["AC-03-001"]["requirements"] == ["03.1", "03.2"]
    assert ac["AC-03-001"]["tests"] == ["tests/b_test.go::TestGamma", "tests/test_a.py::test_alpha",
                                        "tests/test_b.py::test_beta"]
    assert ac["AC-03-002"]["tests"] == ["tests/b_test.go::TestGamma", "tests/test_b.py::test_beta"]


def test_missing_owner_inputs_are_asked_for_all_at_once(project):
    setup(project, owner={"latency_p95_ms": 41})
    r = build(project)
    assert r.returncode == 2 and not (project / "evidence" / "phase-03.json").exists()
    assert "manual_restore" in r.stdout and "evidence/phase-03.owner.json" in r.stdout
    (project / "evidence" / "phase-03.owner.json").unlink()
    r = build(project)
    assert r.returncode == 2 and "latency_p95_ms" in r.stdout and "manual_restore" in r.stdout


def test_a_failing_result_command_is_recorded_and_fails_the_build(project):
    setup(project, {**CFG, "result_command": "false", "owner_inputs": None})
    r = build(project)
    assert r.returncode == 1
    rep = json.loads((project / "evidence" / "phase-03.json").read_text())
    assert rep["result"]["outcome"] == "failed" and rep["result"]["exit_code"] == 1
    r = run("phase-evidence-report", "evidence.py", "check", "--phase", "03", "--config", "skill.json", cwd=project)
    assert r.returncode == 1 and "result: false failed" in r.stdout


def test_check_finds_tests_the_report_names_that_do_not_exist(project):
    setup(project, {**CFG, "owner_inputs": None})
    assert build(project).returncode == 0
    assert run("phase-evidence-report", "evidence.py", "check", "--phase", "03", "--config", "skill.json",
               cwd=project).returncode == 0
    (project / "tests" / "test_b.py").write_text("def test_other():\n    pass\n")
    r = run("phase-evidence-report", "evidence.py", "check", "--phase", "03", "--config", "skill.json", cwd=project)
    assert r.returncode == 1 and "tests/test_b.py::test_beta" in r.stdout


def test_defaults_need_no_config_file(project):
    (project / "docs" / "tasks").mkdir(parents=True)
    (project / "docs" / "tasks" / "phase-03.json").write_text((project / "plans" / "phase-03.json").read_text())
    r = run("phase-evidence-report", "evidence.py", "build", "--phase", "03", cwd=project)
    assert r.returncode == 0, r.stderr
    assert (project / "evidence" / "phase-03.json").exists()
