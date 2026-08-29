# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Steps for `boost doctor` scenarios needing on-disk fixture state."""
from __future__ import annotations

from behave import given


@given("a broken skill symlink exists")
def step_broken_symlink(context):
    from boost_cli.core import paths
    ghost = paths.home() / ".claude" / "skills" / "ghost"
    ghost.parent.mkdir(parents=True, exist_ok=True)
    ghost.symlink_to(paths.store_dir() / "nowhere")
