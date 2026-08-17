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


#: The 91 bytes libFuzzer minimised to on 2026-08-15, decoded the way the
#: harness does: `0x38` then ninety `0xff`, each of which is un-decodable and so
#: becomes U+FFFD — three UTF-8 bytes apiece, 271 bytes for the name alone.
TOO_LONG = "8" + "�" * 90


class TestAnOverlongSpecIsRejected:
    """The second thing the fuzzer found, and the same shape as the first.

    ``p.exists()`` looks total and is not. ``pathlib`` swallows only ENOENT,
    ENOTDIR, EBADF and ELOOP; **ENAMETOOLONG is not in that set**, so on a
    filesystem with a 255-byte component limit — ext4, which is to say every
    Linux runner and most users — a long enough spec makes ``os.stat`` raise
    straight through ``parse_spec``. macOS does not reproduce it, which is why
    only the scheduled Linux fuzz job ever saw it.

    Rejecting is not the whole fix. A *legitimate* long path (a deep directory
    with a short basename) must still parse, so the probe treats "too long for
    this OS" as "not an existing directory" and the length rule applies to the
    derived NAME, which is what becomes a single component under
    ``~/.boost/repos``.
    """

    def test_the_fuzzer_reproducer_raises_boost_error(self):
        with pytest.raises(BoostError):
            registry.parse_spec(TOO_LONG)

    def test_an_overlong_owner_repo_is_rejected(self):
        """Plain ASCII reaches the same limit, it just takes 256 of them."""
        with pytest.raises(BoostError):
            registry.parse_spec("owner/" + "r" * 300)

    def test_the_error_names_the_problem(self):
        """Only for a spec that *parses* — the fuzzer's own reproducer carries
        no separator, so it is rejected as unparseable and never reaches the
        length rule. Both paths raise BoostError, which is the invariant; this
        pins the message on the one where length is the actual reason."""
        with pytest.raises(BoostError) as caught:
            registry.parse_spec("owner/" + "r" * 300)
        assert "too long" in str(caught.value).lower()

    def test_the_limit_is_on_bytes_not_characters(self):
        """A component limit is a *byte* limit, and non-ASCII costs more.

        90 characters is nothing; 90 U+FFFD is 270 bytes and does not fit.
        Measuring characters would let exactly the fuzzer's input through.
        """
        assert len(TOO_LONG) < 255 < len(TOO_LONG.encode("utf-8"))
        with pytest.raises(BoostError):
            registry.parse_spec(TOO_LONG)

    def test_a_probe_that_cannot_stat_is_not_an_existing_directory(self, tmp_path):
        """The OS refusing to look is a "no", not a crash.

        This is the assertion that actually fails on Linux without the fix:
        the spec is a path shape, so it reaches the filesystem probe before any
        length rule could have rejected it.
        """
        spec = str(tmp_path / ("d" * 400))
        with pytest.raises(BoostError):
            registry.parse_spec(spec)

    def test_a_stat_that_raises_reads_as_not_a_directory(self):
        """Pinned on every platform, because it only *fails* on one.

        macOS returns False where Linux raises ENAMETOOLONG, so a test that
        relies on a real long path proves nothing on the machine most of this
        is written on — and this bug reached production precisely because the
        scheduled Linux job was the only thing that ever saw it.
        """
        class Raises:
            def is_dir(self):
                raise OSError(36, "File name too long")

        assert registry._looks_like_a_directory(Raises()) is False

    def test_a_stat_that_succeeds_is_still_a_directory(self, tmp_path):
        """The guard must not swallow the answer it exists to return."""
        assert registry._looks_like_a_directory(tmp_path) is True
        assert registry._looks_like_a_directory(tmp_path / "nope") is False

    def test_the_rejection_carries_a_hint(self):
        """A BoostError with no hint is the CLI printing a dead end.

        Every other rejection in `parse_spec` says what to do instead, and this
        one has something specific to say: the name is about to become a
        directory, which is why the limit is what it is.
        """
        with pytest.raises(BoostError) as caught:
            registry.parse_spec("owner/" + "r" * 300)
        assert caught.value.hint
        assert "~/.boost/repos" in caught.value.hint

    def test_a_url_whose_derived_name_is_too_long_names_the_spec(self):
        """The URL branch derives a name too, and the error must be traceable
        back to what the user typed rather than to the name we computed."""
        with pytest.raises(BoostError) as caught:
            registry.parse_spec("https://github.com/owner/" + "r" * 300)
        assert "owner" in str(caught.value)

    def test_a_long_path_with_a_short_basename_still_parses(self, tmp_path):
        """The rule is about the derived name, never the spec's own length."""
        deep = tmp_path
        for _ in range(6):
            deep = deep / ("segment-" + "x" * 30)
        deep = deep / "my-tap"
        deep.mkdir(parents=True)
        assert len(str(deep)) > 255
        name, url = registry.parse_spec(str(deep))
        assert name == "my-tap"
        assert url == str(deep.resolve())

    def test_a_name_at_the_limit_is_still_accepted(self):
        """Reject one byte over, not one byte under — the boundary is pinned
        because an off-by-one here silently turns away a legal repo name."""
        name = "o" * 100 + "/" + "r" * 154        # 255 bytes exactly
        assert len(name.encode("utf-8")) == 255
        assert registry.parse_spec(name)[0] == name


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
