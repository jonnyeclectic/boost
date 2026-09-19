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


class TestDocsPythonFloor:
    """The docs' own install lines must name the same floor.

    Nine of the eleven docs pages' footers moved to 3.12 with the floor; the
    two roadmap boards' footers — hand-authored outside the regions
    `build_roadmap.py` regenerates, so `--check` stayed green — kept saying
    3.9, as did the design board's "targets Python ≥ 3.9". Stock macOS
    `python3` is 3.9, so that is the reader the stale floor misleads.
    """

    def test_every_footer_names_requires_python(self):
        major, minor = _requires_python_floor()
        pages = sorted((ROOT / "docs").glob("*.html"))
        footers = {page.name: [ln.strip() for ln in
                               page.read_text(encoding="utf-8").splitlines()
                               if 'class="foot-note"' in ln]
                   for page in pages}
        # One footer per page, found by its class alone — so a page that
        # loses its footer, or rewords it away from "requires Python", fails
        # here rather than dropping out of the scan.
        assert pages and all(len(f) == 1 for f in footers.values()), footers
        stale = {name: f[0] for name, f in footers.items()
                 if "requires Python %d.%d+" % (major, minor) not in f[0]}
        assert not stale, stale

    def test_design_board_targets_the_same_floor(self):
        major, minor = _requires_python_floor()
        text = (ROOT / "docs" / "design-roadmap.html").read_text(encoding="utf-8")
        assert re.findall(r"targets <code>Python ≥ (\d+\.\d+)</code>", text) \
            == ["%d.%d" % (major, minor)]
