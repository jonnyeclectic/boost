# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A test that never asks for `sandbox` still runs in a throwaway home."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import conftest

from boost_cli.core import paths


def test_home_is_the_session_home_not_the_real_one():
    home = Path(os.environ["HOME"])
    assert home.name.startswith("boost-test-home-")
    assert home.parent == Path(tempfile.gettempdir())
    assert paths.home() == home


def test_boost_state_resolves_inside_the_session_home():
    home = Path(os.environ["HOME"])
    assert paths.boost_home().is_relative_to(home)


def test_relocating_variables_are_dropped():
    for name in conftest._RELOCATING_ENV:
        assert name not in os.environ, name


def test_a_child_process_inherits_the_session_home():
    out = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ['HOME'])"],
        capture_output=True, text=True, encoding="utf-8", check=True)
    assert out.stdout.strip() == os.environ["HOME"]


def test_sandbox_still_replaces_it(sandbox):
    assert Path(os.environ["HOME"]) == sandbox
    assert not sandbox.name.startswith("boost-test-home-")
