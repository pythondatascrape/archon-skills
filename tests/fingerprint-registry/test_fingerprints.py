import hashlib
import json

from conftest import run


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def setup(project):
    reg = {"versions": {"1": {"frozen": True, "files": {"tests/test_a.py": "0" * 64, "tests/test_b.py": "0" * 64}}}}
    (project / "compat.json").write_text(json.dumps(reg, indent=2))


def fp(project, *args):
    return run("fingerprint-registry", "fingerprints.py", *args, "--file", "compat.json",
               "--pointer", "/versions/1/files", cwd=project)


def test_check_lists_every_stale_fingerprint(project):
    setup(project)
    r = fp(project, "check")
    assert r.returncode == 1 and "tests/test_a.py" in r.stdout and "tests/test_b.py" in r.stdout


def test_update_rewrites_only_the_hashes_and_keeps_the_rest(project):
    setup(project)
    assert fp(project, "update").returncode == 0
    reg = json.loads((project / "compat.json").read_text())
    assert reg["versions"]["1"]["frozen"] is True
    assert reg["versions"]["1"]["files"] == {"tests/test_a.py": sha(project / "tests/test_a.py"),
                                             "tests/test_b.py": sha(project / "tests/test_b.py")}
    assert fp(project, "check").returncode == 0


def test_add_registers_a_new_file(project):
    setup(project)
    fp(project, "update")
    assert fp(project, "update", "--add", "tests/b_test.go").returncode == 0
    files = json.loads((project / "compat.json").read_text())["versions"]["1"]["files"]
    assert files["tests/b_test.go"] == sha(project / "tests/b_test.go")


def test_a_missing_file_is_an_error_not_a_hash(project):
    setup(project)
    (project / "tests" / "test_b.py").unlink()
    r = fp(project, "update")
    assert r.returncode == 1 and "tests/test_b.py" in r.stdout
    assert json.loads((project / "compat.json").read_text())["versions"]["1"]["files"]["tests/test_b.py"] == "0" * 64


def test_a_bad_pointer_is_reported(project):
    setup(project)
    r = run("fingerprint-registry", "fingerprints.py", "check", "--file", "compat.json", "--pointer", "/nope",
            cwd=project)
    assert r.returncode == 2 and "/nope" in r.stdout
