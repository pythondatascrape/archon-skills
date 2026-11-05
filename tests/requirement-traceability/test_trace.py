import json

from conftest import run


def trace(project, *extra):
    return run("requirement-traceability", "trace.py", "--plan", "plans/phase-03.json", *extra, cwd=project)


def test_every_requirement_traced_to_existing_tests(project):
    r = trace(project, "--out", "trace.json")
    assert r.returncode == 0, r.stdout + r.stderr
    t = json.loads((project / "trace.json").read_text())
    assert t["requirements"]["03.1"] == ["tests/test_a.py::test_alpha"]
    assert t["requirements"]["AC-03-002"] == ["tests/b_test.go::TestGamma", "tests/test_b.py::test_beta"]
    assert t["problems"] == []


def test_a_test_missing_from_its_file_is_reported(project):
    (project / "tests" / "b_test.go").write_text("package b\n")
    r = trace(project)
    assert r.returncode == 1 and "tests/b_test.go::TestGamma" in r.stdout and "03.2" in r.stdout


def test_a_requirement_with_no_test_is_reported(project):
    p = json.loads((project / "plans" / "phase-03.json").read_text())
    p["tasks"].append({"task_id": "03.3", "requirements": ["03.3"], "tests": []})
    (project / "plans" / "phase-03.json").write_text(json.dumps(p))
    r = trace(project)
    assert r.returncode == 1 and "03.3" in r.stdout and "no test" in r.stdout


def test_only_requirements_matching_a_pattern(project):
    r = trace(project, "--pattern", "^AC-", "--out", "t.json")
    assert r.returncode == 0
    assert sorted(json.loads((project / "t.json").read_text())["requirements"]) == ["AC-03-001", "AC-03-002"]


def test_name_must_be_a_whole_word(project):
    (project / "tests" / "test_a.py").write_text("def test_alphabet():\n    pass\n")
    r = trace(project)
    assert r.returncode == 1 and "tests/test_a.py::test_alpha" in r.stdout



def test_a_go_subtest_is_found_by_its_function_and_its_t_run_name(tmp_path):
    """Plans name Go subtests as TestX/case; the file has `func TestX` and `t.Run("case", ...)`
    (a Go project's phase 11 plan: 42 subtests reported missing that all exist)."""
    import json as j
    from conftest import task
    (tmp_path / "x_test.go").write_text('package x\n\nfunc TestAC1(t *testing.T) {\n'
                                        '\tt.Run("evidence-recorded", func(t *testing.T) {})\n}\n')
    (tmp_path / "plan.json").write_text(j.dumps({"tasks": [
        task("01.1", ["01.1"], [("x_test.go", "TestAC1/evidence-recorded")]),
        task("01.2", ["01.2"], [("x_test.go", "TestAC1/missing-case")]),
        task("01.3", ["01.3"], [("x_test.go", "TestAC2/evidence-recorded")])]}))
    r = run("requirement-traceability", "trace.py", "--plan", "plan.json", cwd=tmp_path)
    assert r.returncode == 1
    assert "01.1:" not in r.stdout
    assert "01.2: x_test.go::TestAC1/missing-case not found" in r.stdout
    assert "01.3: x_test.go::TestAC2/evidence-recorded not found" in r.stdout
