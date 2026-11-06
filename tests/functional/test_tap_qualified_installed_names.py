# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: every command that acts on an installed item takes ``tap:name``.

``install fix:brainstorming`` works, and every ambiguity hint tells the user to
type the qualified form — but uninstall, pin, unpin, reinstall, quarantine,
verify, drift, lint, test, attest, impact and focus probed the lock (keyed by
the bare name) with the qualified string and answered "not installed" about
an item ``boost list`` shows. They now go through ``store.installed_name``.
"""
from __future__ import annotations

import shutil

import pytest

from boost_cli.core import lockfile


@pytest.fixture()
def qtap(boost, fixture_tap_src, tmp_path, request):
    """A fixture tap under a name unique to this test, with brainstorming
    installed from it by its qualified name. Returns the tap's lock name."""
    slug = "q-" + request.node.name.replace("[", "-").replace("]", "")[-40:]
    tap_dir = tmp_path / slug
    shutil.copytree(fixture_tap_src, tap_dir)
    boost("tap", tap_dir)
    boost("install", "%s:brainstorming" % slug)
    tap = lockfile.get_skill("brainstorming")["tap"]
    assert tap.split("/")[-1] == slug
    return tap


@pytest.mark.parametrize("argv", [
    ("verify",), ("drift",), ("lint",), ("test",), ("attest",), ("impact",),
    ("reinstall",),
], ids=lambda a: a[0])
def test_a_read_command_accepts_the_qualified_name(boost, qtap, argv):
    r = boost(*argv, "%s:brainstorming" % qtap)
    assert "not installed" not in r.out + r.err
    assert "brainstorming" in r.out


def test_the_repo_tail_is_a_qualifier_too(boost, qtap):
    boost("pin", "%s:brainstorming" % qtap.split("/")[-1])
    assert lockfile.get_skill("brainstorming")["pinned"] is True


def test_pin_and_unpin(boost, qtap):
    r = boost("pin", "%s:brainstorming" % qtap)
    assert "pinned brainstorming" in r.out
    assert lockfile.get_skill("brainstorming")["pinned"] is True
    boost("unpin", "%s:brainstorming" % qtap)
    assert not lockfile.get_skill("brainstorming").get("pinned")


def test_quarantine_and_release(boost, qtap):
    boost("quarantine", "%s:brainstorming" % qtap)
    assert lockfile.get_skill("brainstorming")["quarantined"] is True
    boost("quarantine", "--release", "%s:brainstorming" % qtap)
    assert lockfile.get_skill("brainstorming")["quarantined"] is False


def test_focus(boost, qtap):
    r = boost("focus", "%s:brainstorming" % qtap)
    assert "not installed" not in r.out + r.err
    boost("focus", "--clear")


def test_uninstall(boost, qtap):
    boost("uninstall", "-y", "%s:brainstorming" % qtap)
    assert lockfile.get_skill("brainstorming") is None


@pytest.mark.parametrize("argv", [
    ("uninstall", "-y"), ("pin",), ("unpin",), ("reinstall",), ("quarantine",),
    ("verify",), ("drift",), ("test",), ("attest",), ("impact",), ("focus",),
], ids=lambda a: a[0])
def test_a_wrong_tap_qualifier_is_refused_and_names_the_real_tap(boost, qtap, argv):
    r = boost(*argv, "elsewhere:brainstorming", expect=1)
    assert ("elsewhere:brainstorming is not installed — brainstorming is "
            "installed from %s, not elsewhere" % qtap) in " ".join(r.err.split())
    # Refused before acting: the install is untouched.
    entry = lockfile.get_skill("brainstorming")
    assert entry is not None
    assert not entry.get("pinned") and not entry.get("quarantined")


def test_a_qualified_name_nothing_is_installed_under_says_not_installed(boost, qtap):
    r = boost("pin", "%s:nope" % qtap, expect=1)
    assert "nope is not installed" in r.err
