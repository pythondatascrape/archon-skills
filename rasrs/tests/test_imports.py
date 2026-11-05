"""Workstream 0 (B2): the rasrs tools import from a plain checkout of the workflow pack.

seed_code.py and recall.py load the pack's .shared code from the installed path
(~/.archon/workflows/tasks/.shared) only, so on a machine without Archon installed (CI, a fresh
clone) the tools could not even be imported and test collection failed. They fall back to the
repository's own .shared/.

Run:  uv run --with pytest pytest -q -p no:cacheprovider skills/rasrs/tests/test_imports.py
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


PACK_SHARED = TOOLS.parents[2] / ".shared"  # the fallback exists only inside a checkout of the workflow pack


@pytest.mark.skipif(not PACK_SHARED.is_dir(), reason="this copy of the skill is not inside the workflow pack, "
                    "so there is no .shared/ to fall back to; the installed pack is used")
@pytest.mark.parametrize("module", ["seed_code", "recall"])
def test_the_tool_and_the_shared_code_it_uses_import_without_an_installed_pack(tmp_path, module):
    env = {**os.environ, "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import {module}; import knowledge"],
                       env=env, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-800:]
