"""Unit tests: a tap spec carrying control characters is rejected at the door.

`parse_spec` used to accept them. Given the ten bytes ``/\\0\\0\\0\\0\\0\\0\\0\\0A`` it
returned a perfectly well-formed pair::

    ('/\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00A',
     'https://github.com//\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00A')

Nothing raised, so the name travelled onward — into ``config.json``, into
``Tap.safe_name``, and eventually into a filesystem call, where it died as
``ValueError: lstat: embedded null character in path`` from deep inside
``posixpath.realpath``. That message names neither the tap nor the command, and
``ValueError`` is not ``BoostError``, so the CLI's error handling never got to
frame it.

This is how the repo found out: ``fuzz.yml`` runs libFuzzer over ``parse_spec``
weekly, and it has failed **three scheduled runs out of three** — 2026-07-25,
08-01 and 08-08 — writing the same reproducer each time. Nobody noticed, because
``ci-failure-issue.yml`` watches only ``["ci", "demo"]``, so a red cron job is a
red square on a page nobody opens. The fuzzer had been right for three weeks.

A control character can never appear in a GitHub owner/repo, a git URL, or a
usable directory name, so there is no input this rejects that anyone wanted.
Rejecting at the parse boundary turns an arbitrary later ``ValueError`` into the
documented ``BoostError`` rejection path — which the fuzz harness already
handles, and which the CLI already renders with a hint.
"""
from __future__ import annotations

import pytest

from boost_cli.core import registry
from boost_cli.errors import BoostError

#: The exact ten bytes libFuzzer minimised to, decoded the way the harness does.
CRASHER = "/\x00\x00\x00\x00\x00\x00\x00\x00A"


class TestControlCharactersAreRejected:
    def test_the_fuzzer_reproducer_raises_boost_error(self):
        with pytest.raises(BoostError):
            registry.parse_spec(CRASHER)

    def test_a_bare_nul_is_rejected(self):
        with pytest.raises(BoostError):
            registry.parse_spec("owner/re\x00po")

    @pytest.mark.parametrize("ch", ["\x00", "\x01", "\x07", "\x1b", "\x7f"])
    def test_every_control_character_is_rejected(self, ch):
        # \x1b in particular: an escape sequence in a name is echoed back by
        # every surface that prints a tap list.
        with pytest.raises(BoostError):
            registry.parse_spec("owner/re%spo" % ch)

    def test_the_error_names_the_problem(self):
        with pytest.raises(BoostError) as caught:
            registry.parse_spec(CRASHER)
        assert "control character" in str(caught.value).lower()

    def test_a_newline_or_tab_is_rejected_too(self):
        # These survive `.strip()` when they are in the middle, and a newline in
        # a tap name breaks every line-oriented output in the CLI.
        for spec in ("owner/re\npo", "owner/re\tpo"):
            with pytest.raises(BoostError):
                registry.parse_spec(spec)


class TestOrdinarySpecsStillParse:
    """The rejection must not widen. Each of these is a documented input."""

    def test_owner_repo(self):
        assert registry.parse_spec("anthropics/skills") == (
            "anthropics/skills", "https://github.com/anthropics/skills")

    def test_an_https_url(self):
        name, url = registry.parse_spec("https://github.com/acme/skills")
        assert name == "acme/skills" and url.startswith("https://")

    def test_an_ssh_url(self):
        name, _url = registry.parse_spec("git@github.com:acme/skills.git")
        assert name == "acme/skills"

    def test_a_local_directory(self, tmp_path):
        target = tmp_path / "my-skills"
        target.mkdir()
        name, url = registry.parse_spec(str(target))
        assert name == "my-skills" and url == str(target.resolve())

    def test_surrounding_whitespace_is_still_only_stripped(self):
        # Leading/trailing whitespace is trimmed, not rejected — that is a
        # paste artifact, not a hostile name, and it always worked.
        assert registry.parse_spec("  acme/skills  ")[0] == "acme/skills"

    def test_a_unicode_name_is_not_a_control_character(self):
        # Non-ASCII is legal in a path and must not be caught by this net.
        assert registry.parse_spec("acmé/skïlls")[0] == "acmé/skïlls"


class TestTheDerivedPathIsNowAlwaysUsable:
    """The property the fuzz harness asserts, and could not reach before.

    Its containment check calls ``os.path.realpath`` on the derived clone
    directory. That is what raised — so the harness could never even evaluate
    the invariant it exists to protect.
    """

    def test_realpath_of_the_derived_path_no_longer_raises(self):
        import os
        with pytest.raises(BoostError):
            name, url = registry.parse_spec(CRASHER)
            # Unreachable once parse_spec rejects; kept so this test fails
            # loudly rather than silently if the rejection is ever removed.
            os.path.realpath(str(registry.Tap(name=name, url=url).path))
