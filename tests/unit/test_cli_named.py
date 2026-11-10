# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`install`'s per-item failure prefix never says the name twice."""
from __future__ import annotations

from boost_cli.commands.pkg import _named


def test_prefixes_a_message_that_does_not_open_with_the_name():
    assert _named("a", "boom") == "a: boom"


def test_leaves_a_message_that_already_opens_with_the_name():
    msg = "jira-integration is already installed (v2.1.0)"
    assert _named("jira-integration", msg) == msg


def test_a_name_that_is_only_a_string_prefix_is_still_prefixed():
    assert _named("a", "abc is broken") == "a: abc is broken"


def test_a_message_opening_with_name_and_colon_is_left_alone():
    assert _named("a", "a: broken") == "a: broken"
