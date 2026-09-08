# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The `./boost` launcher's Python floor must track `requires-python`.

The launcher shim finds an interpreter and rejects anything below its own
hardcoded floor *before* ever importing boost_cli, so it cannot read
`requires-python` out of pyproject.toml at runtime — the floor is duplicated
by hand in three places (a comment, the version-check tuple, and the
"not found" hint). The `python-floor-moves-to-312` migration bumped
pyproject.toml's `requires-python` to `>=3.12` and missed all three, so a
stock macOS whose only `python3` is 3.9 kept passing the launcher's own gate
and hit a SyntaxError out of `core/workflows.py`'s match statements instead
of a friendly "Python 3.12+ is required" message. Pinning the comparison here
means the next floor bump fails this test until the launcher moves with it.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "boost"


def _requires_python_floor() -> tuple[int, int]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = pyproject["project"]["requires-python"]
    m = re.match(r">=(\d+)\.(\d+)$", requires)
    assert m, "unexpected requires-python spec: %r" % requires
    return int(m.group(1)), int(m.group(2))


class TestLauncherPythonFloor:
    def test_version_check_tuple_matches_requires_python(self):
        major, minor = _requires_python_floor()
        text = LAUNCHER.read_text(encoding="utf-8")
        assert "sys.version_info >= (%d, %d)" % (major, minor) in text

    def test_header_comment_names_the_same_floor(self):
        major, minor = _requires_python_floor()
        text = LAUNCHER.read_text(encoding="utf-8")
        assert "finds Python %d.%d+" % (major, minor) in text

    def test_not_found_hint_names_the_same_floor(self):
        major, minor = _requires_python_floor()
        text = LAUNCHER.read_text(encoding="utf-8")
        assert "Python %d.%d+ is required" % (major, minor) in text
