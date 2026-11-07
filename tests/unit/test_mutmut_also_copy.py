# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit test: every repo-root file the unit suite reads is in mutmut's also_copy.

mutmut runs ``tests/unit`` inside ``mutants/``, a copy of the repo holding only
``tests/``, ``setup.cfg``, ``pyproject.toml`` and whatever ``also_copy`` in
setup.cfg names. A unit test that opens a root file left out of that list fails
there with ``FileNotFoundError: .../mutants/<file>``, which fails mutmut's
baseline. Every mutation shard then goes red without naming ``boost_cli``, on
a change that touched no product code. That happened with the Makefile,
``.lighthouserc.json``, ``MANIFEST.in`` and then ``SUPPORT.md``, each found
only in CI. This test finds it locally instead.

It is a static scan, so it sees only the convention the suite uses: a
module-level name bound to the repo root (``Path(__file__)...parents[2]`` or
``.parent.parent.parent``) joined with a string literal.
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# What mutmut copies into mutants/ without being told (see setup.cfg's header).
IMPLICIT = {"tests", "setup.cfg", "pyproject.toml"}

# Root entries a unit test may read that are deliberately NOT copied: the tests
# that read .git skip when the checkout has no history, as mutants/ does not.
NOT_COPIED = {".git"}

_ROOT_BINDING = re.compile(
    r"^(?P<name>[A-Z_][A-Z0-9_]*)\s*=\s*Path\(__file__\)\.resolve\(\)"
    r"(?:\.parents\[2\]|\.parent\.parent\.parent)\s*$",
    re.MULTILINE,
)


def also_copy() -> set[str]:
    """The top-level names setup.cfg's ``[mutmut] also_copy`` lists."""
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "setup.cfg", encoding="utf-8")
    entries = (line.strip() for line in cfg["mutmut"]["also_copy"].splitlines())
    return {e.rstrip("/").split("/")[0] for e in entries
            if e and not e.startswith("#")}


def root_entries_read_by_unit_tests() -> dict[str, set[str]]:
    """Top-level repo entry -> the unit test files that join it onto the root."""
    found: dict[str, set[str]] = {}
    for path in sorted((ROOT / "tests" / "unit").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in {m.group("name") for m in _ROOT_BINDING.finditer(text)}:
            use = re.compile(r"\b%s\s*/\s*[\"']([^\"'/]+)" % re.escape(name))
            for m in use.finditer(text):
                top = m.group(1)
                if (ROOT / top).exists():
                    found.setdefault(top, set()).add(path.name)
    return found


def test_the_scan_sees_the_files_it_exists_for():
    # Guard the guard: if the suite's root-joining convention changed, the
    # scan would find nothing and the test below would pass vacuously.
    found = root_entries_read_by_unit_tests()
    assert {"README.md", "Makefile", "SUPPORT.md"} <= set(found)


def test_every_root_file_a_unit_test_reads_is_copied_into_mutants():
    copied = also_copy() | IMPLICIT | NOT_COPIED
    missing = {top: sorted(files)
               for top, files in root_entries_read_by_unit_tests().items()
               if top not in copied}
    assert missing == {}, (
        "add these to [mutmut] also_copy in setup.cfg, or mutmut's baseline "
        "fails inside mutants/: %r" % missing)
