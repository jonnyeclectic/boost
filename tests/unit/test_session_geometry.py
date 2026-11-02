# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""No test inherits a terminal width it did not set.

Under pytest-xdist on Linux every worker used to start with COLUMNS=80 and
LINES=24, put there by GNU readline in the controller (see
``conftest._GEOMETRY_ENV``), and every table was fitted to 80 columns.
"""
from __future__ import annotations

import os
import subprocess
import sys

import conftest

from boost_cli.core import output


def test_the_session_starts_with_no_terminal_geometry():
    for name in conftest._GEOMETRY_ENV:
        assert name not in os.environ, name


def test_a_captured_stream_has_no_pane():
    # What every functional test's `boost` runner relies on: capsys is not a
    # terminal, so a table is emitted whole unless the test sets COLUMNS.
    assert output.pane_width() is None


def test_a_child_process_inherits_no_geometry():
    out = subprocess.run(
        [sys.executable, "-c",
         "import os; print(os.environ.get('COLUMNS'), os.environ.get('LINES'))"],
        capture_output=True, text=True, encoding="utf-8", check=True)
    assert out.stdout.split() == ["None", "None"]


def test_drop_inherited_geometry_removes_both(monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setenv("LINES", "24")
    conftest._drop_inherited_geometry()
    assert "COLUMNS" not in os.environ
    assert "LINES" not in os.environ
