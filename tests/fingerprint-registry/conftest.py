"""Fixtures for this skill's tests: a throwaway project with a phase plan."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "fingerprint-registry"


def run(skill: str, script: str, *args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SKILL / "scripts" / script), *args],
                          cwd=cwd, capture_output=True, text=True)


def task(tid: str, requirements: list[str], tests: list[tuple[str, str]]) -> dict:
    return {"task_id": tid, "requirements": requirements,
            "tests": [{"name": n, "file": f} for f, n in tests]}


@pytest.fixture
def project(tmp_path):
    """A git project with a phase 03 plan of two tasks and the three tests they name."""
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "plans").mkdir()
    (root / "plans" / "phase-03.json").write_text(json.dumps({"phase_id": "03", "tasks": [
        task("03.1", ["03.1", "AC-03-001"], [("tests/test_a.py", "test_alpha")]),
        task("03.2", ["03.2", "AC-03-001", "AC-03-002"], [("tests/test_b.py", "test_beta"),
                                                          ("tests/b_test.go", "TestGamma")]),
    ]}))
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_alpha():\n    assert True\n")
    (root / "tests" / "test_b.py").write_text("def test_beta():\n    assert True\n")
    (root / "tests" / "b_test.go").write_text("package b\n\nfunc TestGamma(t *testing.T) {}\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=root, check=True)
    return root
