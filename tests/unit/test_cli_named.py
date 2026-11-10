# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""`install`'s per-item failure prefix never says the name twice."""
from __future__ import annotations

from boost_cli.commands.pkg import _named


def test_prefixes_a_message_that_does_not_open_with_the_name():
    assert _named("a", "boom") == "a: boom"


def test_leaves_a_message_that_already_opens_with_the_name():
    msg = "jira-integration is already installed (v2.1.0)"
    assert _named("jira-integration", msg) == msg
